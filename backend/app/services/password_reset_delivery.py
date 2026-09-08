from __future__ import annotations

from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
)

from typing import (
    Protocol,
)


# =========================================================
# DELIVERY MESSAGE
# =========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class PasswordResetDeliveryMessage:
    """
    Information required by a password-reset delivery
    provider.

    reset_url contains the one-time bearer credential and is
    therefore sensitive.

    Never:

        log the full URL
        persist the full URL
        include it in security telemetry
        expose it from the password-reset request endpoint
    """

    recipient_email: str

    reset_url: str

    expires_at: datetime


# =========================================================
# DELIVERY ERRORS
# =========================================================


class PasswordResetDeliveryError(
    Exception
):
    """
    Base exception for failures while delivering password
    recovery instructions.

    Provider-specific exceptions should be translated into
    this application-level error rather than leaking AWS,
    SMTP, or vendor implementation details upward.
    """

    pass


# =========================================================
# DELIVERY CONTRACT
# =========================================================


class PasswordResetDelivery(
    Protocol
):
    """
    Transport-independent password-reset delivery contract.

    Implementations might eventually include:

        AWS SES
        SMTP
        another transactional-email provider
    """

    def send_password_reset(
        self,
        message: PasswordResetDeliveryMessage,
    ) -> None:
        ...