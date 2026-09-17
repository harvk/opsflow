from collections.abc import Collection
from uuid import uuid4

import httpx
import pytest

from app.core.service_identity import ServiceScope
from app.core.service_token_provider import ServiceTokenCreationError
from app.gateways.http_service_catalog_gateway import HttpServiceCatalogGateway
from app.services.exceptions import ServiceCatalogUnavailableError

CORE_BACKEND_URL = "http://core-backend.test/api/v1"
CORE_BACKEND_AUDIENCE = "opsflow-core-backend"
SERVICE_TOKEN = "signed-incident-service-token"


class RecordingServiceTokenProvider:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[
            tuple[str, frozenset[ServiceScope]]
        ] = []

    def create_token(
        self,
        *,
        audience: str,
        scopes: Collection[ServiceScope],
    ) -> str:
        self.calls.append(
            (audience, frozenset(scopes))
        )
        if self.fail:
            raise ServiceTokenCreationError(
                "sensitive-signing-detail"
            )
        return SERVICE_TOKEN


def build_gateway(
    handler: httpx.MockTransport,
    provider: RecordingServiceTokenProvider,
) -> tuple[HttpServiceCatalogGateway, httpx.Client]:
    client = httpx.Client(transport=handler)
    gateway = HttpServiceCatalogGateway(
        client=client,
        core_backend_url=CORE_BACKEND_URL,
        service_token_provider=provider,
        core_backend_audience=CORE_BACKEND_AUDIENCE,
    )
    return gateway, client


def test_service_exists_uses_services_read_bearer_token() -> None:
    service_id = uuid4()
    provider = RecordingServiceTokenProvider()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url == httpx.URL(
            f"{CORE_BACKEND_URL}/internal/services/"
            f"{service_id}/exists"
        )
        assert request.headers["Authorization"] == (
            f"Bearer {SERVICE_TOKEN}"
        )
        assert "X-OpsFlow-Internal-Token" not in request.headers
        return httpx.Response(200, json={"exists": True})

    gateway, client = build_gateway(
        httpx.MockTransport(handler),
        provider,
    )
    try:
        assert gateway.service_exists(service_id) is True
    finally:
        client.close()

    assert provider.calls == [
        (
            CORE_BACKEND_AUDIENCE,
            frozenset({ServiceScope.SERVICES_READ}),
        )
    ]


def test_service_exists_returns_false() -> None:
    provider = RecordingServiceTokenProvider()
    gateway, client = build_gateway(
        httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={"exists": False},
            )
        ),
        provider,
    )
    try:
        assert gateway.service_exists(uuid4()) is False
    finally:
        client.close()


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(503),
        httpx.Response(200, json={"exists": "true"}),
    ],
)
def test_invalid_remote_response_fails_closed(
    response: httpx.Response,
) -> None:
    provider = RecordingServiceTokenProvider()
    gateway, client = build_gateway(
        httpx.MockTransport(lambda _request: response),
        provider,
    )
    try:
        with pytest.raises(ServiceCatalogUnavailableError):
            gateway.service_exists(uuid4())
    finally:
        client.close()


def test_network_failure_fails_closed() -> None:
    provider = RecordingServiceTokenProvider()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            "Connection unavailable.",
            request=request,
        )

    gateway, client = build_gateway(
        httpx.MockTransport(handler),
        provider,
    )
    try:
        with pytest.raises(ServiceCatalogUnavailableError):
            gateway.service_exists(uuid4())
    finally:
        client.close()


def test_token_creation_failure_is_sanitized() -> None:
    transport_attempted = False

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal transport_attempted
        transport_attempted = True
        return httpx.Response(200)

    gateway, client = build_gateway(
        httpx.MockTransport(handler),
        RecordingServiceTokenProvider(fail=True),
    )
    try:
        with pytest.raises(
            ServiceCatalogUnavailableError
        ) as captured_error:
            gateway.service_exists(uuid4())
    finally:
        client.close()

    assert not transport_attempted
    assert "sensitive-signing-detail" not in str(
        captured_error.value
    )
    assert captured_error.value.__cause__ is None
