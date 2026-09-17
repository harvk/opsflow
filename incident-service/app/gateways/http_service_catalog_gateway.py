from uuid import (
    UUID,
)

import httpx

from app.core.service_identity import (
    ServiceIdentityError,
    ServiceScope,
)
from app.core.service_token_provider import (
    ServiceTokenCreationError,
    ServiceTokenProvider,
)
from app.services.exceptions import (
    ServiceCatalogUnavailableError,
)


class HttpServiceCatalogGateway:
    """
    HTTP implementation of the Service Catalog boundary.

    All transport, authentication, status-code, and response
    contract failures are translated into the stable Incident
    application error contract.
    """

    def __init__(
        self,
        *,
        client: httpx.Client,
        core_backend_url: str,
        service_token_provider: ServiceTokenProvider,
        core_backend_audience: str,
    ) -> None:
        self._client = client

        self._core_backend_url = (
            core_backend_url
            .rstrip("/")
        )

        self._service_token_provider = (
            service_token_provider
        )

        self._core_backend_audience = (
            core_backend_audience.strip()
        )

        if not self._core_backend_audience:
            raise ValueError(
                "core_backend_audience must not be empty."
            )

    def service_exists(
        self,
        service_id: UUID,
    ) -> bool:
        endpoint = (
            f"{self._core_backend_url}"
            "/internal/services/"
            f"{service_id}/exists"
        )

        try:
            token = (
                self
                ._service_token_provider
                .create_token(
                    audience=(
                        self
                        ._core_backend_audience
                    ),
                    scopes={
                        ServiceScope.SERVICES_READ
                    },
                )
            )

            if not isinstance(token, str) or not token:
                raise ServiceTokenCreationError(
                    "The service-token provider returned "
                    "an invalid credential."
                )

            response = (
                self._client
                .get(
                    endpoint,
                    headers={
                        "Authorization": (
                            f"Bearer {token}"
                        ),
                    },
                )
            )

        except ServiceIdentityError:
            raise self._unavailable(
                service_id
            ) from None

        except httpx.RequestError as exc:
            raise self._unavailable(
                service_id
            ) from exc

        if response.status_code != 200:
            raise self._unavailable(
                service_id
            )

        try:
            payload: object = (
                response.json()
            )

        except ValueError as exc:
            raise self._unavailable(
                service_id
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise self._unavailable(
                service_id
            )

        exists = payload.get(
            "exists"
        )

        if type(exists) is not bool:
            raise self._unavailable(
                service_id
            )

        return exists

    @staticmethod
    def _unavailable(
        service_id: UUID,
    ) -> ServiceCatalogUnavailableError:
        return (
            ServiceCatalogUnavailableError(
                "Service Catalog validation "
                "is unavailable. "
                "Could not validate Service "
                f"{service_id}."
            )
        )
