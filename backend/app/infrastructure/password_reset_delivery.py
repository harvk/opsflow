from __future__ import annotations

from app.services.password_reset_delivery import (
    PasswordResetDeliveryMessage,
)


class DiscardingPasswordResetDelivery:
    """
    Temporary password-reset delivery adapter.

    This implementation deliberately performs no network
    activity and retains no reset credential.

    It exists only so the application can exercise the
    delivery abstraction before the AWS SES adapter is
    introduced.

    It must not be the final production delivery mechanism.
    """

    def send_password_reset(
        self,
        message: PasswordResetDeliveryMessage,
    ) -> None:
        # Deliberately discard the message.
        #
        # Do not log:
        #
        #     message.reset_url
        #
        # because it contains the raw bearer credential.
        return None