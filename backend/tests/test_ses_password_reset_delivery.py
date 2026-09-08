from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

import pytest

from botocore.exceptions import (
    ClientError,
)

from app.infrastructure.aws.ses_password_reset_delivery import (
    SesPasswordResetDelivery,
)

from app.services.password_reset_delivery import (
    PasswordResetDeliveryError,
    PasswordResetDeliveryMessage,
)

from tests.fakes.ses_client import (
    RecordingSesClient,
)


RESET_URL = (
    "https://app.example.com/"
    "reset-password"
    "?token=very-secret-reset-token"
)


def build_message(
) -> PasswordResetDeliveryMessage:
    return (
        PasswordResetDeliveryMessage(
            recipient_email=(
                "user@example.com"
            ),
            reset_url=(
                RESET_URL
            ),
            expires_at=(
                datetime(
                    2026,
                    9,
                    7,
                    18,
                    30,
                    tzinfo=(
                        timezone.utc
                    ),
                )
            ),
        )
    )


# =========================================================
# BASIC SES REQUEST
# =========================================================


def test_ses_delivery_sends_to_expected_recipient(
) -> None:
    client = (
        RecordingSesClient()
    )

    delivery = (
        SesPasswordResetDelivery(
            client=client,
            sender_email=(
                "no-reply@example.com"
            ),
        )
    )

    delivery.send_password_reset(
        build_message()
    )

    assert len(
        client.requests
    ) == 1

    request = (
        client.requests[0]
    )

    assert (
        request[
            "FromEmailAddress"
        ]
        == "no-reply@example.com"
    )

    assert (
        request[
            "Destination"
        ][
            "ToAddresses"
        ]
        == [
            "user@example.com"
        ]
    )


# =========================================================
# SUBJECT AND BODY
# =========================================================


def test_ses_delivery_constructs_subject_and_bodies(
) -> None:
    client = (
        RecordingSesClient()
    )

    delivery = (
        SesPasswordResetDelivery(
            client=client,
            sender_email=(
                "no-reply@example.com"
            ),
        )
    )

    delivery.send_password_reset(
        build_message()
    )

    simple = (
        client.requests[0]
        ["Content"]
        ["Simple"]
    )

    assert (
        simple[
            "Subject"
        ][
            "Data"
        ]
        == "Reset your OpsFlow password"
    )

    text_body = (
        simple[
            "Body"
        ][
            "Text"
        ][
            "Data"
        ]
    )

    html_body = (
        simple[
            "Body"
        ][
            "Html"
        ][
            "Data"
        ]
    )

    assert (
        RESET_URL
        in text_body
    )

    assert (
        "2026-09-07 18:30 UTC"
        in text_body
    )

    assert (
        "Reset your password"
        in html_body
    )

    assert (
        "2026-09-07 18:30 UTC"
        in html_body
    )


# =========================================================
# CONFIGURATION SET
# =========================================================


def test_ses_delivery_includes_configuration_set_when_present(
) -> None:
    client = (
        RecordingSesClient()
    )

    delivery = (
        SesPasswordResetDelivery(
            client=client,
            sender_email=(
                "no-reply@example.com"
            ),
            configuration_set_name=(
                "opsflow-email"
            ),
        )
    )

    delivery.send_password_reset(
        build_message()
    )

    assert (
        client.requests[0][
            "ConfigurationSetName"
        ]
        == "opsflow-email"
    )


def test_ses_delivery_omits_configuration_set_when_absent(
) -> None:
    client = (
        RecordingSesClient()
    )

    delivery = (
        SesPasswordResetDelivery(
            client=client,
            sender_email=(
                "no-reply@example.com"
            ),
        )
    )

    delivery.send_password_reset(
        build_message()
    )

    assert (
        "ConfigurationSetName"
        not in client.requests[0]
    )


# =========================================================
# VALIDATION
# =========================================================


def test_ses_delivery_rejects_empty_sender(
) -> None:
    with pytest.raises(
        ValueError
    ):
        SesPasswordResetDelivery(
            client=(
                RecordingSesClient()
            ),
            sender_email=" ",
        )


def test_ses_delivery_rejects_empty_recipient(
) -> None:
    delivery = (
        SesPasswordResetDelivery(
            client=(
                RecordingSesClient()
            ),
            sender_email=(
                "no-reply@example.com"
            ),
        )
    )

    message = (
        PasswordResetDeliveryMessage(
            recipient_email=" ",
            reset_url=(
                RESET_URL
            ),
            expires_at=(
                datetime.now(
                    timezone.utc
                )
            ),
        )
    )

    with pytest.raises(
        PasswordResetDeliveryError
    ):
        delivery.send_password_reset(
            message
        )


def test_ses_delivery_rejects_naive_expiration(
) -> None:
    delivery = (
        SesPasswordResetDelivery(
            client=(
                RecordingSesClient()
            ),
            sender_email=(
                "no-reply@example.com"
            ),
        )
    )

    message = (
        PasswordResetDeliveryMessage(
            recipient_email=(
                "user@example.com"
            ),
            reset_url=(
                RESET_URL
            ),
            expires_at=(
                datetime(
                    2026,
                    9,
                    7,
                    18,
                    30,
                )
            ),
        )
    )

    with pytest.raises(
        PasswordResetDeliveryError
    ):
        delivery.send_password_reset(
            message
        )