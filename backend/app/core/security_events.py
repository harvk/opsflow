from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import logging
from typing import Literal
from uuid import UUID, uuid4

from fastapi import Request

from app.core.config import settings


SecurityOutcome = Literal[
    "success",
    "failure",
    "blocked",
]


# =========================================================
# SECURITY LOGGER
# =========================================================


class SecurityEventLogger:
    """
    Emit structured, machine-readable security events.

    The logger deliberately records only metadata required
    for security monitoring and investigation.

    It must never receive or record:

        passwords
        access tokens
        refresh tokens
        CSRF tokens
        Authorization headers
        Cookie headers
        cryptographic keys
        complete request bodies
    """

    LOGGER_NAME = "opsflow.security"

    def __init__(
        self,
        *,
        hmac_key: str,
        logger: logging.Logger | None = None,
    ) -> None:
        if not hmac_key:
            raise ValueError(
                "A security-event HMAC key is required."
            )

        self._hmac_key = hmac_key.encode(
            "utf-8"
        )

        self._logger = (
            logger
            if logger is not None
            else logging.getLogger(
                self.LOGGER_NAME
            )
        )

        # INFO is necessary because successful authentication
        # events are intentionally auditable.
        self._logger.setLevel(
            logging.INFO
        )

    # =====================================================
    # PUBLIC EVENT API
    # =====================================================

    def emit(
        self,
        *,
        event: str,
        outcome: SecurityOutcome,
        level: int,
        request: Request | None = None,
        user_id: UUID | str | None = None,
        account_identifier: str | None = None,
        reason: str | None = None,
        details: Mapping[
            str,
            str | int | bool | None,
        ]
        | None = None,
    ) -> None:
        """
        Emit one structured security event.

        Logging failures must never turn a successful or
        intentionally rejected authentication request into
        an application failure.
        """

        try:
            payload: dict[
                str,
                object,
            ] = {
                "event_id": str(
                    uuid4()
                ),
                "occurred_at": (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                ),
                "event": self._clean_text(
                    event
                ),
                "outcome": outcome,
                "severity": (
                    logging.getLevelName(
                        level
                    ).lower()
                ),
            }

            if request is not None:
                payload[
                    "client_address"
                ] = self._client_address(
                    request
                )

                payload[
                    "http_method"
                ] = request.method

                # Deliberately log the route path only.
                #
                # Query strings can contain sensitive
                # information and are unnecessary here.
                payload[
                    "http_path"
                ] = request.url.path

            if user_id is not None:
                payload[
                    "user_id"
                ] = self._clean_text(
                    str(
                        user_id
                    )
                )

            if account_identifier is not None:
                payload[
                    "account_fingerprint"
                ] = (
                    self.account_fingerprint(
                        account_identifier
                    )
                )

            if reason is not None:
                payload[
                    "reason"
                ] = self._clean_text(
                    reason
                )

            if details:
                payload[
                    "details"
                ] = {
                    self._clean_text(
                        str(key)
                    ): self._clean_value(
                        value
                    )
                    for key, value
                    in details.items()
                }

            serialized = json.dumps(
                payload,
                separators=(
                    ",",
                    ":",
                ),
                sort_keys=True,
            )

            self._logger.log(
                level,
                serialized,
            )

        except Exception:
            # Security telemetry is extremely important,
            # but failure of the logging subsystem must not
            # break authentication or create information
            # disclosure.
            #
            # A production monitoring layer should separately
            # detect unavailable log delivery.
            return

    # =====================================================
    # IDENTIFIER PSEUDONYMIZATION
    # =====================================================

    def account_fingerprint(
        self,
        account_identifier: str,
    ) -> str:
        """
        Produce a stable pseudonymous identifier.

        Different capitalization or surrounding whitespace
        maps to the same value:

            USER@example.com
            user@example.com
            " user@example.com "

        all produce the same fingerprint.
        """

        normalized = (
            account_identifier
            .strip()
            .lower()
        )

        message = (
            f"account:{normalized}"
            .encode(
                "utf-8"
            )
        )

        return hmac.new(
            self._hmac_key,
            message,
            sha256,
        ).hexdigest()

    # =====================================================
    # REQUEST METADATA
    # =====================================================

    @staticmethod
    def _client_address(
        request: Request,
    ) -> str:
        """
        Use only the client identity already established by
        the ASGI server.

        Do not trust X-Forwarded-For directly here.
        """

        if request.client is None:
            return "unknown"

        return request.client.host

    # =====================================================
    # LOG INJECTION / SIZE DEFENSE
    # =====================================================

    @staticmethod
    def _clean_text(
        value: str,
        *,
        max_length: int = 256,
    ) -> str:
        """
        Bound attacker-influenced fields and remove literal
        control characters that could make logs confusing.

        json.dumps() also escapes control characters, but
        sanitizing here provides an additional invariant.
        """

        cleaned = (
            value
            .replace(
                "\r",
                " "
            )
            .replace(
                "\n",
                " "
            )
            .replace(
                "\t",
                " "
            )
        )

        return cleaned[
            :max_length
        ]

    @classmethod
    def _clean_value(
        cls,
        value: str | int | bool | None,
    ) -> str | int | bool | None:
        if isinstance(
            value,
            str,
        ):
            return cls._clean_text(
                value
            )

        return value


# =========================================================
# PROCESS-WIDE LOGGER
# =========================================================


security_event_logger = (
    SecurityEventLogger(
        hmac_key=(
            settings
            .security_event_hmac_key
            .get_secret_value()
        )
    )
)