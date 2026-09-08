from __future__ import annotations

from typing import (
    Any,
)

from botocore.exceptions import (
    ClientError,
)


class RecordingSesClient:
    """
    Test double for boto3's SES v2 client.

    It records send_email() requests without making network
    calls to AWS.
    """

    def __init__(
        self,
    ) -> None:
        self.requests: list[
            dict[
                str,
                Any,
            ]
        ] = []

    def send_email(
        self,
        **kwargs: Any,
    ) -> dict[
        str,
        Any,
    ]:
        self.requests.append(
            kwargs
        )

        return {
            "MessageId": (
                "test-message-id"
            )
        }


class FailingSesClient:
    """
    Test double for boto3's SES v2 client that simulates an
    AWS SES message-rejection failure.

    This allows the SES delivery adapter to verify that AWS
    ClientError exceptions are translated into the
    application-level PasswordResetDeliveryError.
    """

    def send_email(
        self,
        **kwargs: Any,
    ) -> dict[
        str,
        Any,
    ]:
        raise ClientError(
            {
                "Error": {
                    "Code": (
                        "MessageRejected"
                    ),
                    "Message": (
                        "SES rejected message."
                    ),
                }
            },
            "SendEmail",
        )