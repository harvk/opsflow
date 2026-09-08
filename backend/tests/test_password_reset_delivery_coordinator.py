from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from uuid import (
    uuid4,
)

from urllib.parse import (
    parse_qs,
    urlsplit,
)

from app.core.password_reset_links import (
    PasswordResetLinkBuilder,
)

from app.services.password_reset_delivery_coordinator import (
    PasswordResetDeliveryCoordinator,
)

from app.services.password_reset_service import (
    PasswordResetIssueResult,
)

from tests.fakes.password_reset_delivery import (
    RecordingPasswordResetDelivery,
)


def test_coordinator_delivers_password_reset_message(
) -> None:
    delivery = (
        RecordingPasswordResetDelivery()
    )

    coordinator = (
        PasswordResetDeliveryCoordinator(
            link_builder=(
                PasswordResetLinkBuilder(
                    reset_url=(
                        "https://app.example.com/"
                        "reset-password"
                    )
                )
            ),
            delivery=(
                delivery
            ),
        )
    )

    expires_at = (
        datetime.now(
            timezone.utc
        )
        + timedelta(
            minutes=30
        )
    )

    issuance = (
        PasswordResetIssueResult(
            user_id=(
                uuid4()
            ),
            email=(
                "user@example.com"
            ),
            raw_token=(
                "super-secret-reset-token"
            ),
            expires_at=(
                expires_at
            ),
        )
    )

    coordinator.deliver(
        issuance
    )

    assert len(
        delivery.messages
    ) == 1

    message = (
        delivery.messages[0]
    )

    assert (
        message.recipient_email
        == "user@example.com"
    )

    assert (
        message.expires_at
        == expires_at
    )

    query = parse_qs(
        urlsplit(
            message.reset_url
        ).query
    )

    assert query[
        "token"
    ] == [
        "super-secret-reset-token"
    ]


def test_coordinator_does_not_modify_issuance(
) -> None:
    delivery = (
        RecordingPasswordResetDelivery()
    )

    coordinator = (
        PasswordResetDeliveryCoordinator(
            link_builder=(
                PasswordResetLinkBuilder(
                    reset_url=(
                        "https://app.example.com/"
                        "reset-password"
                    )
                )
            ),
            delivery=(
                delivery
            ),
        )
    )

    issuance = (
        PasswordResetIssueResult(
            user_id=(
                uuid4()
            ),
            email=(
                "user@example.com"
            ),
            raw_token=(
                "original-token"
            ),
            expires_at=(
                datetime.now(
                    timezone.utc
                )
                + timedelta(
                    minutes=30
                )
            ),
        )
    )

    coordinator.deliver(
        issuance
    )

    assert (
        issuance.raw_token
        == "original-token"
    )