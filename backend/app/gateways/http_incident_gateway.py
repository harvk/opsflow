from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx
from pydantic import TypeAdapter, ValidationError

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


class HttpIncidentGateway:
    """
    HTTP adapter for the IncidentGateway contract.

    The adapter translates Core Backend domain operations
    into the Incident Service's private HTTP contract. It
    owns transport concerns only; authorization and business
    rules remain in their respective application services.
    """

    def __init__(
        self,
        *,
        client: httpx.Client,
        incident_service_url: str,
        internal_token: str,
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

        self._client = client
        self._incidents_url = (
            f"{normalized_url}/incidents"
        )
        self._headers = {
            "Accept": "application/json",
            "X-OpsFlow-Internal-Token": internal_token,
        }

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
        params: dict[str, str | int] = {
            "offset": offset,
            "limit": limit,
        }

        if search is not None:
            params["search"] = search

        if service_id is not None:
            params["serviceId"] = str(service_id)

        if severity is not None:
            params["severity"] = severity.value

        if status is not None:
            params["status"] = status.value

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
            f"{self._incidents_url}/{incident_id}",
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
            f"{self._incidents_url}/{incident_id}",
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
            f"{self._incidents_url}/{incident_id}",
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
        try:
            return self._client.request(
                method,
                url,
                headers=self._headers,
                params=params,
                json=json,
            )

        except httpx.TimeoutException:
            raise IncidentGatewayUnavailableError(
                "Incident Service request timed out."
            ) from None

        except httpx.RequestError:
            raise IncidentGatewayUnavailableError(
                "Incident Service is unavailable."
            ) from None

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
            for item in validated_items
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