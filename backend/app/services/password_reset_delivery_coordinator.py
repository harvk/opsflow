from __future__ import annotations

from app.core.password_reset_links import (
    PasswordResetLinkBuilder,
)

from app.services.password_reset_delivery import (
    PasswordResetDelivery,
    PasswordResetDeliveryMessage,
)

from app.services.password_reset_service import (
    PasswordResetIssueResult,
)


class PasswordResetDeliveryCoordinator:
    """
    Converts an internally issued password-reset credential
    into a browser-facing recovery link and hands it to the
    configured delivery provider.

    This class deliberately owns no persistence logic and no
    email-provider logic.
    """

    def __init__(
        self,
        *,
        link_builder: PasswordResetLinkBuilder,
        delivery: PasswordResetDelivery,
    ) -> None:
        self.link_builder = (
            link_builder
        )

        self.delivery = (
            delivery
        )

    def deliver(
        self,
        issuance: PasswordResetIssueResult,
    ) -> None:
        reset_url = (
            self.link_builder
            .build(
                raw_token=(
                    issuance.raw_token
                ),
            )
        )

        message = (
            PasswordResetDeliveryMessage(
                recipient_email=(
                    issuance.email
                ),
                reset_url=(
                    reset_url
                ),
                expires_at=(
                    issuance.expires_at
                ),
            )
        )

        self.delivery.send_password_reset(
            message
        )