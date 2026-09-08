from __future__ import annotations

from app.services.password_reset_delivery import (
    PasswordResetDeliveryMessage,
)


class RecordingPasswordResetDelivery:
    def __init__(
        self,
    ) -> None:
        self.messages: list[
            PasswordResetDeliveryMessage
        ] = []

    def send_password_reset(
        self,
        message: PasswordResetDeliveryMessage,
    ) -> None:
        self.messages.append(
            message
        )