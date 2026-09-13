from uuid import (
    uuid4,
)

import httpx
import pytest

from app.gateways.http_service_catalog_gateway import (
    HttpServiceCatalogGateway,
)
from app.services.exceptions import (
    ServiceCatalogUnavailableError,
)

CORE_BACKEND_URL = (
    "http://core-backend.test/api/v1"
)

INTERNAL_TOKEN = (
    "test-internal-token-that-is-"
    "at-least-32-characters"
)


def test_service_exists_sends_token_and_returns_true(
) -> None:
    service_id = uuid4()

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "GET"

        assert request.url == httpx.URL(
            
                f"{CORE_BACKEND_URL}"
                "/internal/services/"
                f"{service_id}/exists"
            
        )

        assert request.headers[
            "X-OpsFlow-Internal-Token"
        ] == INTERNAL_TOKEN

        return httpx.Response(
            200,
            json={
                "exists": True,
            },
        )

    with httpx.Client(
        transport=httpx.MockTransport(
            handler
        ),
    ) as client:
        gateway = (
            HttpServiceCatalogGateway(
                client=client,
                core_backend_url=(
                    CORE_BACKEND_URL
                ),
                internal_token=(
                    INTERNAL_TOKEN
                ),
            )
        )

        assert (
            gateway.service_exists(
                service_id
            )
            is True
        )


def test_service_exists_returns_false(
) -> None:
    def handler(
        _request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "exists": False,
            },
        )

    with httpx.Client(
        transport=httpx.MockTransport(
            handler
        ),
    ) as client:
        gateway = (
            HttpServiceCatalogGateway(
                client=client,
                core_backend_url=(
                    CORE_BACKEND_URL
                ),
                internal_token=(
                    INTERNAL_TOKEN
                ),
            )
        )

        assert (
            gateway.service_exists(
                uuid4()
            )
            is False
        )


def test_non_success_status_fails_closed(
) -> None:
    def handler(
        _request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            503
        )

    with httpx.Client(
        transport=httpx.MockTransport(
            handler
        ),
    ) as client:
        gateway = (
            HttpServiceCatalogGateway(
                client=client,
                core_backend_url=(
                    CORE_BACKEND_URL
                ),
                internal_token=(
                    INTERNAL_TOKEN
                ),
            )
        )

        with pytest.raises(
            ServiceCatalogUnavailableError
        ):
            gateway.service_exists(
                uuid4()
            )


def test_invalid_response_contract_fails_closed(
) -> None:
    def handler(
        _request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "exists": "true",
            },
        )

    with httpx.Client(
        transport=httpx.MockTransport(
            handler
        ),
    ) as client:
        gateway = (
            HttpServiceCatalogGateway(
                client=client,
                core_backend_url=(
                    CORE_BACKEND_URL
                ),
                internal_token=(
                    INTERNAL_TOKEN
                ),
            )
        )

        with pytest.raises(
            ServiceCatalogUnavailableError
        ):
            gateway.service_exists(
                uuid4()
            )


def test_network_failure_fails_closed(
) -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        raise httpx.ConnectError(
            "Connection unavailable.",
            request=request,
        )

    with httpx.Client(
        transport=httpx.MockTransport(
            handler
        ),
    ) as client:
        gateway = (
            HttpServiceCatalogGateway(
                client=client,
                core_backend_url=(
                    CORE_BACKEND_URL
                ),
                internal_token=(
                    INTERNAL_TOKEN
                ),
            )
        )

        with pytest.raises(
            ServiceCatalogUnavailableError
        ):
            gateway.service_exists(
                uuid4()
            )