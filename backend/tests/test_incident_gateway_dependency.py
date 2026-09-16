from collections.abc import (
    Collection,
)
from typing import cast

import httpx
import pytest

from app.api import dependencies
from app.core.service_identity import (
    ServiceScope,
)
from app.gateways.http_incident_gateway import (
    HttpIncidentGateway,
)
from app.gateways.local_incident_gateway import (
    LocalIncidentGateway,
)
from app.services.incident_service import IncidentService


class StubIncidentService:
    pass


class StubServiceTokenProvider:
    def create_token(
        self,
        *,
        audience: str,
        scopes: Collection[
            ServiceScope
        ],
    ) -> str:
        if not audience:
            raise AssertionError(
                "Audience must not be empty."
            )

        if not scopes:
            raise AssertionError(
                "Scopes must not be empty."
            )

        return "stub-service-token"


def test_local_mode_uses_local_incident_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called() -> httpx.Client:
        raise AssertionError(
            "HTTP client must not be created in local mode."
        )

    def fail_service_provider_if_called(
    ) -> object:
        raise AssertionError(
            "Service-token provider must not be "
            "created in local mode."
        )

    monkeypatch.setattr(
        dependencies.settings,
        "incident_gateway_mode",
        "local",
    )
    monkeypatch.setattr(
        dependencies,
        "get_incident_http_client",
        fail_if_called,
    )
    monkeypatch.setattr(
        dependencies,
        "get_service_token_provider",
        fail_service_provider_if_called,
    )

    gateway = dependencies.get_incident_gateway(
        cast(
            IncidentService,
            StubIncidentService(),
        )
    )

    assert isinstance(
        gateway,
        LocalIncidentGateway,
    )


def test_http_mode_uses_http_incident_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                500
            )
        )
    )

    monkeypatch.setattr(
        dependencies.settings,
        "incident_gateway_mode",
        "http",
    )
    monkeypatch.setattr(
        dependencies,
        "get_incident_http_client",
        lambda: client,
    )
    monkeypatch.setattr(
        dependencies,
        "get_service_token_provider",
        StubServiceTokenProvider,
    )

    try:
        gateway = dependencies.get_incident_gateway(
            cast(
                IncidentService,
                StubIncidentService(),
            )
        )

        assert isinstance(
            gateway,
            HttpIncidentGateway,
        )

    finally:
        client.close()