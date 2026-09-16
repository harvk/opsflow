from __future__ import annotations

from collections.abc import (
    Callable,
)
from time import (
    monotonic,
    sleep,
)
from typing import (
    Any,
)
from uuid import (
    UUID,
)

import httpx
from pydantic import (
    TypeAdapter,
    ValidationError,
)

from app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitPermit,
)
from app.core.metrics import (
    OperationalMetrics,
)
from app.core.request_context import (
    REQUEST_ID_HEADER,
    get_request_id,
)
from app.core.service_identity import (
    ServiceIdentityError,
    ServiceScope,
    ServiceTokenCreationError,
    ServiceTokenProvider,
)
from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from app.gateways.incident_gateway import (
    IncidentGatewayCircuitOpenError,
    IncidentGatewayProtocolError,
    IncidentGatewayUnavailableError,
)
from app.schemas.incident import (
    IncidentCreate,
    IncidentResponse,
    IncidentUpdate,
)
from app.services.incident_service import (
    IncidentNotFoundError,
    IncidentServiceReferenceError,
)

_INCIDENT_LIST_ADAPTER = TypeAdapter(
    list[IncidentResponse]
)

_RETRYABLE_READ_METHODS = frozenset(
    {
        "GET",
        "HEAD",
        "OPTIONS",
    }
)

_RETRYABLE_RESPONSE_STATUSES = frozenset(
    {
        502,
        503,
        504,
    }
)

_INCIDENT_SERVICE_DEPENDENCY = (
    "incident_service"
)


class HttpIncidentGateway:
    """
    HTTP adapter for the IncidentGateway contract.

    The adapter translates Core Backend domain operations
    into the Incident Service's private HTTP contract. It
    owns transport concerns only; authorization and business
    rules remain in their respective application services.

    Safe read operations receive a bounded retry policy.
    Mutating operations are attempted exactly once because
    the Incident Service does not currently expose idempotency
    keys for mutation deduplication.

    Every outbound request carries a short-lived, scoped
    service bearer credential. Read operations receive only
    incidents:read; mutations receive only incidents:write.
    The removed shared-secret header is never transmitted.
    """

    def __init__(
        self,
        *,
        client: httpx.Client,
        incident_service_url: str,
        service_token_provider: ServiceTokenProvider,
        incident_service_audience: str,
        read_max_attempts: int = 1,
        read_backoff_seconds: float = 0.0,
        sleeper: Callable[
            [float],
            None,
        ] = sleep,
        circuit_breaker: (
            CircuitBreaker
            | None
        ) = None,
        metrics: (
            OperationalMetrics
            | None
        ) = None,
    ) -> None:
        normalized_url = (
            incident_service_url
            .strip()
            .rstrip("/")
        )

        if not normalized_url:
            raise ValueError(
                "incident_service_url must not be empty."
            )

        if service_token_provider is None:
            raise ValueError(
                "service_token_provider is required."
            )

        normalized_audience = (
            incident_service_audience.strip()
        )

        if not normalized_audience:
            raise ValueError(
                "incident_service_audience must not be empty."
            )

        if read_max_attempts < 1:
            raise ValueError(
                "read_max_attempts must be at least 1."
            )

        if read_backoff_seconds < 0:
            raise ValueError(
                "read_backoff_seconds must not be negative."
            )

        self._client = client

        self._incidents_url = (
            f"{normalized_url}/incidents"
        )

        self._headers = {
            "Accept": "application/json",
        }

        self._service_token_provider = (
            service_token_provider
        )

        self._incident_service_audience = (
            normalized_audience
        )

        self._read_max_attempts = (
            read_max_attempts
        )

        self._read_backoff_seconds = (
            read_backoff_seconds
        )

        self._sleeper = sleeper

        self._circuit_breaker = (
            circuit_breaker
        )

        self._metrics = metrics

        self._observe_circuit_state()

    # =====================================================
    # LIST / SEARCH
    # =====================================================

    def list(
        self,
        *,
        search: str | None = None,
        service_id: UUID | None = None,
        severity: IncidentSeverity | None = None,
        status: IncidentStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Incident]:
        params: dict[
            str,
            str | int,
        ] = {
            "offset": offset,
            "limit": limit,
        }

        if search is not None:
            params[
                "search"
            ] = search

        if service_id is not None:
            params[
                "serviceId"
            ] = str(
                service_id
            )

        if severity is not None:
            params[
                "severity"
            ] = severity.value

        if status is not None:
            params[
                "status"
            ] = status.value

        response = self._request(
            "GET",
            self._incidents_url,
            params=params,
        )

        self._require_status(
            response,
            expected_status=200,
        )

        return self._parse_incident_list(
            response
        )

    # =====================================================
    # GET BY ID
    # =====================================================

    def get_by_id(
        self,
        incident_id: UUID,
    ) -> Incident:
        response = self._request(
            "GET",
            (
                f"{self._incidents_url}/"
                f"{incident_id}"
            ),
        )

        if response.status_code == 404:
            raise IncidentNotFoundError(
                self._response_detail(
                    response,
                    fallback=(
                        "Incident not found."
                    ),
                )
            )

        self._require_status(
            response,
            expected_status=200,
        )

        return self._parse_incident(
            response
        )

    # =====================================================
    # CREATE
    # =====================================================

    def create(
        self,
        payload: IncidentCreate,
    ) -> Incident:
        response = self._request(
            "POST",
            self._incidents_url,
            json=payload.model_dump(
                mode="json",
                by_alias=True,
            ),
        )

        if response.status_code == 404:
            raise IncidentServiceReferenceError(
                self._response_detail(
                    response,
                    fallback=(
                        "Referenced service not found."
                    ),
                )
            )

        self._require_status(
            response,
            expected_status=201,
        )

        return self._parse_incident(
            response
        )

    # =====================================================
    # UPDATE
    # =====================================================

    def update(
        self,
        incident_id: UUID,
        payload: IncidentUpdate,
    ) -> Incident:
        response = self._request(
            "PATCH",
            (
                f"{self._incidents_url}/"
                f"{incident_id}"
            ),
            json=payload.model_dump(
                mode="json",
                by_alias=True,
                exclude_unset=True,
            ),
        )

        if response.status_code == 404:
            raise IncidentNotFoundError(
                self._response_detail(
                    response,
                    fallback=(
                        "Incident not found."
                    ),
                )
            )

        if response.status_code == 400:
            raise IncidentServiceReferenceError(
                self._response_detail(
                    response,
                    fallback=(
                        "Referenced service not found."
                    ),
                )
            )

        self._require_status(
            response,
            expected_status=200,
        )

        return self._parse_incident(
            response
        )

    # =====================================================
    # DELETE
    # =====================================================

    def delete(
        self,
        incident_id: UUID,
    ) -> None:
        response = self._request(
            "DELETE",
            (
                f"{self._incidents_url}/"
                f"{incident_id}"
            ),
        )

        if response.status_code == 404:
            raise IncidentNotFoundError(
                self._response_detail(
                    response,
                    fallback=(
                        "Incident not found."
                    ),
                )
            )

        self._require_status(
            response,
            expected_status=204,
        )

    # =====================================================
    # SERVICE-SCOPED LIST
    # =====================================================

    def list_for_service(
        self,
        service_id: UUID,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Incident]:
        return self.list(
            service_id=service_id,
            offset=offset,
            limit=limit,
        )

    # =====================================================
    # HTTP TRANSPORT
    # =====================================================

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: (
            dict[str, str | int]
            | None
        ) = None,
        json: (
            dict[str, Any]
            | None
        ) = None,
    ) -> httpx.Response:
        normalized_method = (
            method.upper()
        )

        operation_started_at = (
            monotonic()
        )

        operation_outcome = (
            "unexpected_error"
        )

        circuit_permit: (
            CircuitPermit
            | None
        ) = None

        try:
            circuit_permit = (
                self._acquire_circuit_permission()
            )

            maximum_attempts = (
                self._read_max_attempts
                if normalized_method
                in _RETRYABLE_READ_METHODS
                else 1
            )

            # A half-open probe receives exactly one physical
            # transport attempt.
            if (
                circuit_permit is not None
                and circuit_permit
                .is_half_open_probe
            ):
                maximum_attempts = 1

            request_headers = dict(
                self._headers
            )

            request_id = get_request_id()

            if request_id is not None:
                request_headers[
                    REQUEST_ID_HEADER
                ] = request_id

            for attempt_number in range(
                1,
                maximum_attempts + 1,
            ):
                try:
                    attempt_headers = dict(
                        request_headers
                    )

                    service_authorization = (
                        self
                        ._create_service_authorization(
                            normalized_method
                        )
                    )

                    attempt_headers[
                        "Authorization"
                    ] = service_authorization

                    response = (
                        self._client.request(
                            normalized_method,
                            url,
                            headers=attempt_headers,
                            params=params,
                            json=json,
                        )
                    )

                except httpx.TimeoutException:
                    self._record_dependency_attempt(
                        method=normalized_method,
                        outcome="timeout",
                    )

                    if (
                        attempt_number
                        >= maximum_attempts
                    ):
                        self._record_circuit_failure(
                            circuit_permit
                        )

                        operation_outcome = (
                            "timeout"
                        )

                        raise IncidentGatewayUnavailableError(
                            "Incident Service request timed out."
                        ) from None

                    self._record_dependency_retry(
                        method=normalized_method,
                        reason="timeout",
                    )

                    self._sleep_before_retry(
                        attempt_number
                    )

                    continue

                except httpx.RequestError:
                    self._record_dependency_attempt(
                        method=normalized_method,
                        outcome=(
                            "transport_error"
                        ),
                    )

                    if (
                        attempt_number
                        >= maximum_attempts
                    ):
                        self._record_circuit_failure(
                            circuit_permit
                        )

                        operation_outcome = (
                            "transport_error"
                        )

                        raise IncidentGatewayUnavailableError(
                            "Incident Service is unavailable."
                        ) from None

                    self._record_dependency_retry(
                        method=normalized_method,
                        reason=(
                            "transport_error"
                        ),
                    )

                    self._sleep_before_retry(
                        attempt_number
                    )

                    continue

                attempt_outcome = (
                    self._response_outcome(
                        response.status_code
                    )
                )

                self._record_dependency_attempt(
                    method=normalized_method,
                    outcome=attempt_outcome,
                )

                if (
                    response.status_code
                    in _RETRYABLE_RESPONSE_STATUSES
                    and attempt_number
                    < maximum_attempts
                ):
                    self._record_dependency_retry(
                        method=normalized_method,
                        reason=(
                            "retryable_status"
                        ),
                    )

                    self._sleep_before_retry(
                        attempt_number
                    )

                    continue

                if (
                    response.status_code
                    >= 500
                ):
                    self._record_circuit_failure(
                        circuit_permit
                    )

                else:
                    self._record_circuit_success(
                        circuit_permit
                    )

                operation_outcome = (
                    attempt_outcome
                )

                return response

            raise RuntimeError(
                "Incident Service retry loop exited unexpectedly."
            )

        except ServiceIdentityError:
            self._record_circuit_failure(
                circuit_permit
            )

            operation_outcome = (
                "authentication_error"
            )

            raise IncidentGatewayUnavailableError(
                "Incident Service authentication "
                "is unavailable."
            ) from None

        except IncidentGatewayCircuitOpenError:
            operation_outcome = (
                "circuit_open"
            )

            raise

        finally:
            self._record_dependency_operation(
                method=normalized_method,
                outcome=operation_outcome,
                duration_seconds=(
                    monotonic()
                    - operation_started_at
                ),
            )

            self._observe_circuit_state()

    def _create_service_authorization(
        self,
        method: str,
    ) -> str:
        scope = (
            ServiceScope.INCIDENTS_READ
            if method
            in _RETRYABLE_READ_METHODS
            else ServiceScope.INCIDENTS_WRITE
        )

        token = (
            self
            ._service_token_provider
            .create_token(
                audience=(
                    self
                    ._incident_service_audience
                ),
                scopes={
                    scope
                },
            )
        )

        if (
            not isinstance(
                token,
                str,
            )
            or not token
        ):
            raise ServiceTokenCreationError(
                "The service-token provider returned "
                "an invalid credential."
            )

        return f"Bearer {token}"

    def _acquire_circuit_permission(
        self,
    ) -> CircuitPermit | None:
        if self._circuit_breaker is None:
            return None

        try:
            return (
                self._circuit_breaker
                .acquire_permission()
            )

        except CircuitOpenError as exc:
            raise (
                IncidentGatewayCircuitOpenError(
                    retry_after_seconds=(
                        exc.retry_after_seconds
                    )
                )
            ) from None

    def _record_circuit_success(
        self,
        permit: CircuitPermit | None,
    ) -> None:
        if (
            self._circuit_breaker is None
            or permit is None
        ):
            return

        self._circuit_breaker.record_success(
            permit
        )

    def _record_circuit_failure(
        self,
        permit: CircuitPermit | None,
    ) -> None:
        if (
            self._circuit_breaker is None
            or permit is None
        ):
            return

        self._circuit_breaker.record_failure(
            permit
        )

    def _record_dependency_operation(
        self,
        *,
        method: str,
        outcome: str,
        duration_seconds: float,
    ) -> None:
        if self._metrics is None:
            return

        self._metrics.observe_dependency_operation(
            dependency=(
                _INCIDENT_SERVICE_DEPENDENCY
            ),
            method=method,
            outcome=outcome,
            duration_seconds=(
                duration_seconds
            ),
        )

    def _record_dependency_attempt(
        self,
        *,
        method: str,
        outcome: str,
    ) -> None:
        if self._metrics is None:
            return

        self._metrics.record_dependency_attempt(
            dependency=(
                _INCIDENT_SERVICE_DEPENDENCY
            ),
            method=method,
            outcome=outcome,
        )

    def _record_dependency_retry(
        self,
        *,
        method: str,
        reason: str,
    ) -> None:
        if self._metrics is None:
            return

        self._metrics.record_dependency_retry(
            dependency=(
                _INCIDENT_SERVICE_DEPENDENCY
            ),
            method=method,
            reason=reason,
        )

    def _observe_circuit_state(
        self,
    ) -> None:
        if (
            self._metrics is None
            or self._circuit_breaker
            is None
        ):
            return

        self._metrics.set_circuit_state(
            dependency=(
                _INCIDENT_SERVICE_DEPENDENCY
            ),
            state=(
                self._circuit_breaker
                .state
                .value
            ),
        )

    @staticmethod
    def _response_outcome(
        status_code: int,
    ) -> str:
        if status_code < 300:
            return "2xx"

        if status_code < 400:
            return "3xx"

        if status_code < 500:
            return "4xx"

        return "5xx"

    def _sleep_before_retry(
        self,
        completed_attempts: int,
    ) -> None:
        delay_seconds = (
            self._read_backoff_seconds
            * (
                2
                ** (
                    completed_attempts
                    - 1
                )
            )
        )

        if delay_seconds <= 0:
            return

        self._sleeper(
            delay_seconds
        )

    # =====================================================
    # HTTP STATUS TRANSLATION
    # =====================================================

    @staticmethod
    def _require_status(
        response: httpx.Response,
        *,
        expected_status: int,
    ) -> None:
        if (
            response.status_code
            == expected_status
        ):
            return

        if response.status_code >= 500:
            raise IncidentGatewayUnavailableError(
                "Incident Service is unavailable."
            )

        raise IncidentGatewayProtocolError(
            "Incident Service returned "
            "an unexpected response."
        )

    # =====================================================
    # RESPONSE DESERIALIZATION
    # =====================================================

    @staticmethod
    def _parse_incident(
        response: httpx.Response,
    ) -> Incident:
        try:
            response_payload = (
                response.json()
            )

            validated = (
                IncidentResponse
                .model_validate(
                    response_payload
                )
            )

        except (
            ValueError,
            ValidationError,
        ) as exc:
            raise IncidentGatewayProtocolError(
                "Incident Service returned "
                "an invalid incident."
            ) from exc

        return Incident(
            **validated.model_dump()
        )

    @staticmethod
    def _parse_incident_list(
        response: httpx.Response,
    ) -> list[Incident]:
        try:
            response_payload = (
                response.json()
            )

            validated_items = (
                _INCIDENT_LIST_ADAPTER
                .validate_python(
                    response_payload
                )
            )

        except (
            ValueError,
            ValidationError,
        ) as exc:
            raise IncidentGatewayProtocolError(
                "Incident Service returned "
                "an invalid incident list."
            ) from exc

        return [
            Incident(
                **item.model_dump()
            )
            for item
            in validated_items
        ]

    # =====================================================
    # REMOTE ERROR DETAIL
    # =====================================================

    @staticmethod
    def _response_detail(
        response: httpx.Response,
        *,
        fallback: str,
    ) -> str:
        try:
            response_payload = (
                response.json()
            )

        except ValueError:
            return fallback

        if not isinstance(
            response_payload,
            dict,
        ):
            return fallback

        detail = response_payload.get(
            "detail"
        )

        if (
            not isinstance(
                detail,
                str,
            )
            or not detail
        ):
            return fallback

        return detail