from __future__ import annotations

from collections.abc import (
    Callable,
)
from time import (
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

from app.core.request_context import (
    REQUEST_ID_HEADER,
    get_request_id,
)
from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from app.gateways.incident_gateway import (
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
    """

    def __init__(
        self,
        *,
        client: httpx.Client,
        incident_service_url: str,
        internal_token: str,
        read_max_attempts: int = 1,
        read_backoff_seconds: float = 0.0,
        sleeper: Callable[
            [float],
            None,
        ] = sleep,
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

        if not internal_token:
            raise ValueError(
                "internal_token must not be empty."
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
            "X-OpsFlow-Internal-Token": internal_token,
        }

        self._read_max_attempts = (
            read_max_attempts
        )

        self._read_backoff_seconds = (
            read_backoff_seconds
        )

        self._sleeper = sleeper

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

        maximum_attempts = (
            self._read_max_attempts
            if normalized_method
            in _RETRYABLE_READ_METHODS
            else 1
        )

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
                response = (
                    self._client.request(
                        normalized_method,
                        url,
                        headers=request_headers,
                        params=params,
                        json=json,
                    )
                )

            except httpx.TimeoutException:
                if (
                    attempt_number
                    >= maximum_attempts
                ):
                    raise IncidentGatewayUnavailableError(
                        "Incident Service request timed out."
                    ) from None

                self._sleep_before_retry(
                    attempt_number
                )

                continue

            except httpx.RequestError:
                if (
                    attempt_number
                    >= maximum_attempts
                ):
                    raise IncidentGatewayUnavailableError(
                        "Incident Service is unavailable."
                    ) from None

                self._sleep_before_retry(
                    attempt_number
                )

                continue

            if (
                response.status_code
                in _RETRYABLE_RESPONSE_STATUSES
                and attempt_number
                < maximum_attempts
            ):
                self._sleep_before_retry(
                    attempt_number
                )

                continue

            return response

        # The loop either returns a response or raises one of
        # the gateway errors above. This guard documents that
        # invariant for static analysis.
        raise RuntimeError(
            "Incident Service retry loop exited unexpectedly."
        )

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