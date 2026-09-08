from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

from html import (
    escape,
)

from typing import (
    Any,
    Protocol,
)

from botocore.exceptions import (
    BotoCoreError,
    ClientError,
)

from app.services.password_reset_delivery import (
    PasswordResetDeliveryError,
    PasswordResetDeliveryMessage,
)


# =========================================================
# MINIMAL SES CLIENT CONTRACT
# =========================================================


class SesClient(
    Protocol
):
    """
    Minimal portion of the boto3 SES v2 client required by
    this adapter.

    Defining our own protocol avoids coupling application
    typing to generated boto3-stubs packages.
    """

    def send_email(
        self,
        **kwargs: Any,
    ) -> dict[
        str,
        Any,
    ]:
        ...


# =========================================================
# AWS SES PASSWORD RESET DELIVERY
# =========================================================


class SesPasswordResetDelivery:
    """
    AWS SES implementation of PasswordResetDelivery.

    Responsibilities:

        construct the password-reset email
        submit it through SES v2
        translate AWS failures into an application-level
        PasswordResetDeliveryError

    The reset URL contains a bearer credential and must
    never be written to logs.
    """

    def __init__(
        self,
        *,
        client: SesClient,
        sender_email: str,
        configuration_set_name: (
            str | None
        ) = None,
    ) -> None:
        normalized_sender = (
            sender_email
            .strip()
        )

        if not normalized_sender:
            raise ValueError(
                "sender_email must not be empty."
            )

        self._client = (
            client
        )

        self._sender_email = (
            normalized_sender
        )

        normalized_configuration_set = (
            configuration_set_name.strip()
            if configuration_set_name
            else None
        )

        self._configuration_set_name = (
            normalized_configuration_set
            or None
        )

    # =====================================================
    # DELIVERY
    # =====================================================

    def send_password_reset(
        self,
        message: PasswordResetDeliveryMessage,
    ) -> None:
        recipient_email = (
            message
            .recipient_email
            .strip()
        )

        if not recipient_email:
            raise PasswordResetDeliveryError(
                "Password reset recipient "
                "is invalid."
            )

        expires_at = (
            self._normalize_expiration(
                message.expires_at
            )
        )

        subject = (
            "Reset your OpsFlow password"
        )

        text_body = (
            self._build_text_body(
                reset_url=(
                    message.reset_url
                ),
                expires_at=(
                    expires_at
                ),
            )
        )

        html_body = (
            self._build_html_body(
                reset_url=(
                    message.reset_url
                ),
                expires_at=(
                    expires_at
                ),
            )
        )

        request: dict[
            str,
            Any,
        ] = {
            "FromEmailAddress": (
                self._sender_email
            ),
            "Destination": {
                "ToAddresses": [
                    recipient_email
                ],
            },
            "Content": {
                "Simple": {
                    "Subject": {
                        "Data": (
                            subject
                        ),
                        "Charset": (
                            "UTF-8"
                        ),
                    },
                    "Body": {
                        "Text": {
                            "Data": (
                                text_body
                            ),
                            "Charset": (
                                "UTF-8"
                            ),
                        },
                        "Html": {
                            "Data": (
                                html_body
                            ),
                            "Charset": (
                                "UTF-8"
                            ),
                        },
                    },
                },
            },
        }

        if (
            self._configuration_set_name
            is not None
        ):
            request[
                "ConfigurationSetName"
            ] = (
                self
                ._configuration_set_name
            )

        try:
            self._client.send_email(
                **request
            )

        except (
            BotoCoreError,
            ClientError,
        ) as exc:
            # Never include message.reset_url in the public
            # application-level exception.
            raise PasswordResetDeliveryError(
                "Password reset email "
                "delivery failed."
            ) from exc

    # =====================================================
    # MESSAGE CONSTRUCTION
    # =====================================================

    @staticmethod
    def _build_text_body(
        *,
        reset_url: str,
        expires_at: datetime,
    ) -> str:
        expiration_text = (
            SesPasswordResetDelivery
            ._format_expiration(
                expires_at
            )
        )

        return (
            "A password reset was requested for your "
            "OpsFlow account.\n\n"
            "Use the following link to choose a new "
            "password:\n\n"
            f"{reset_url}\n\n"
            "This link expires at "
            f"{expiration_text}.\n\n"
            "If you did not request a password reset, "
            "you can ignore this message."
        )

    @staticmethod
    def _build_html_body(
        *,
        reset_url: str,
        expires_at: datetime,
    ) -> str:
        expiration_text = (
            SesPasswordResetDelivery
            ._format_expiration(
                expires_at
            )
        )

        safe_reset_url = (
            escape(
                reset_url,
                quote=True,
            )
        )

        safe_expiration = (
            escape(
                expiration_text
            )
        )

        return (
            "<!doctype html>"
            "<html>"
            "<body>"
            "<p>"
            "A password reset was requested for your "
            "OpsFlow account."
            "</p>"
            "<p>"
            "<a href=\""
            f"{safe_reset_url}"
            "\">"
            "Reset your password"
            "</a>"
            "</p>"
            "<p>"
            "This link expires at "
            f"{safe_expiration}."
            "</p>"
            "<p>"
            "If you did not request a password reset, "
            "you can ignore this message."
            "</p>"
            "</body>"
            "</html>"
        )

    # =====================================================
    # DATETIME HELPERS
    # =====================================================

    @staticmethod
    def _normalize_expiration(
        expires_at: datetime,
    ) -> datetime:
        if (
            expires_at.tzinfo
            is None
        ):
            raise PasswordResetDeliveryError(
                "Password reset expiration "
                "must be timezone-aware."
            )

        return (
            expires_at
            .astimezone(
                timezone.utc
            )
        )

    @staticmethod
    def _format_expiration(
        expires_at: datetime,
    ) -> str:
        return (
            expires_at
            .strftime(
                "%Y-%m-%d %H:%M UTC"
            )
        )