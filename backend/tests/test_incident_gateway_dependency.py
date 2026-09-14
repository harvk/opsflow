from typing import cast

import httpx
import pytest

from app.api import dependencies
from app.gateways.http_incident_gateway import (
    HttpIncidentGateway,
)
from app.gateways.local_incident_gateway import (
    LocalIncidentGateway,
)
from app.services.incident_service import IncidentService


class StubIncidentService:
    pass


def test_local_mode_uses_local_incident_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called() -> httpx.Client:
        raise AssertionError(
            "HTTP client must not be created in local mode."
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