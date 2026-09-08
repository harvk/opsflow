from __future__ import annotations

from typing import (
    Any,
)

import pytest

import app.api.dependencies as dependencies

from app.api.dependencies import (
    get_password_reset_delivery,
    get_ses_client,
)

from app.core.config import (
    settings,
)

from app.infrastructure.aws.ses_password_reset_delivery import (
    SesPasswordResetDelivery,
)

from tests.fakes.ses_client import (
    RecordingSesClient,
)


def test_ses_client_uses_configured_region(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recording_client = (
        RecordingSesClient()
    )

    captured: dict[
        str,
        Any,
    ] = {}

    def fake_boto3_client(
        service_name: str,
        **kwargs: Any,
    ):
        captured[
            "service_name"
        ] = service_name

        captured.update(
            kwargs
        )

        return (
            recording_client
        )

    monkeypatch.setattr(
        dependencies.boto3,
        "client",
        fake_boto3_client,
    )

    get_ses_client.cache_clear()

    try:
        client = (
            get_ses_client()
        )

        assert (
            client
            is recording_client
        )

        assert (
            captured[
                "service_name"
            ]
            == "ses"
        )

        assert (
            captured[
                "region_name"
            ]
            == settings.aws_region
        )

    finally:
        get_ses_client.cache_clear()


def test_password_reset_delivery_uses_ses_adapter(
) -> None:
    client = (
        RecordingSesClient()
    )

    delivery = (
        get_password_reset_delivery(
            ses_client=client
        )
    )

    assert isinstance(
        delivery,
        SesPasswordResetDelivery,
    )