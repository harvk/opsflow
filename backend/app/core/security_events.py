from __future__ import annotations

from collections.abc import (
    Mapping,
)

from datetime import (
    datetime,
    timezone,
)

from hashlib import (
    sha256,
)

import hmac
import json
import logging

from typing import (
    Literal,
)

from uuid import (
    UUID,
    uuid4,
)

from fastapi import (
    Request,
)

from app.core.config import (
    settings,
)


# =========================================================
# SECURITY EVENT TYPES
# =========================================================


SecurityOutcome = Literal[
    "success",
    "failure",
    "blocked",
]


SecurityDetailValue = (
    str
    | int
    | bool
    | None
)


SecurityDetails = Mapping[
    str,
    SecurityDetailValue,
]


# =========================================================
# SECURITY LOGGER
# =========================================================


class SecurityEventLogger:
    """
    Emit structured, machine-readable security events.

    The logger deliberately records only metadata required
    for security monitoring and investigation.

    Callers should never intentionally supply:

        passwords
        access tokens
        refresh tokens
        reset tokens
        CSRF tokens
        reauthentication tokens
        Authorization headers
        Cookie headers
        API keys
        client secrets
        cryptographic keys
        complete request bodies

    This class nevertheless treats the logging boundary as
    defense in depth.

    If a future caller accidentally places a credential in a
    recognized sensitive details field, the value is replaced
    before serialization and therefore cannot reach the
    underlying logging sink.
    """

    LOGGER_NAME = (
        "opsflow.security"
    )

    REDACTED_DETAIL_VALUE = (
        "[REDACTED]"
    )


    # =====================================================
    # SENSITIVE DETAIL-KEY MARKERS
    # =====================================================
    #
    # Detail keys are normalized before comparison:
    #
    #     access_token
    #     access-token
    #     accessToken
    #     ACCESS_TOKEN
    #
    # all become:
    #
    #     accesstoken
    #
    # This makes simple casing or punctuation differences
    # unable to bypass the defensive redaction boundary.
    #
    # We deliberately use security-oriented fragments rather
    # than requiring callers to use one exact spelling.
    # =====================================================


    SENSITIVE_DETAIL_KEY_MARKERS = (
        "password",
        "passwd",
        "token",
        "secret",
        "authorization",
        "cookie",
        "apikey",
        "privatekey",
        "signingkey",
        "hmackey",
        "bearer",
        "credential",
    )


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

        self._hmac_key = (
            hmac_key.encode(
                "utf-8"
            )
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
        details: SecurityDetails | None = None,
    ) -> None:
        """
        Emit one structured security event.

        Logging failures must never turn a successful or
        intentionally rejected authentication request into
        an application failure.

        Structured details remain deliberately limited to
        flat scalar metadata:

            str
            int
            bool
            None

        Arbitrary nested structures and request objects do
        not belong in the security-event details contract.
        """

        try:
            payload: dict[
                str,
                object,
            ] = {
                "event_id": (
                    str(
                        uuid4()
                    )
                ),
                "occurred_at": (
                    datetime.now(
                        timezone.utc
                    )
                    .isoformat()
                ),
                "event": (
                    self._clean_text(
                        event
                    )
                ),
                "outcome": (
                    outcome
                ),
                "severity": (
                    logging
                    .getLevelName(
                        level
                    )
                    .lower()
                ),
            }


            # =================================================
            # SAFE REQUEST METADATA
            # =================================================
            #
            # Do not serialize:
            #
            #     request.headers
            #     Authorization
            #     Cookie
            #     request.url.query
            #     request.scope
            #     request body
            #
            # Only explicitly selected metadata crosses the
            # security-event boundary.
            # =================================================


            if (
                request
                is not None
            ):
                payload[
                    "client_address"
                ] = (
                    self._client_address(
                        request
                    )
                )

                payload[
                    "http_method"
                ] = (
                    self._clean_text(
                        request.method
                    )
                )

                # Deliberately log the route path only.
                #
                # Query strings can contain recovery bearer
                # credentials and are unnecessary here.

                payload[
                    "http_path"
                ] = (
                    self._clean_text(
                        request.url.path
                    )
                )


            # =================================================
            # USER IDENTIFIER
            # =================================================


            if (
                user_id
                is not None
            ):
                payload[
                    "user_id"
                ] = (
                    self._clean_text(
                        str(
                            user_id
                        )
                    )
                )


            # =================================================
            # ACCOUNT IDENTIFIER
            # =================================================
            #
            # Email/account identifiers are pseudonymized
            # before entering logs.
            # =================================================


            if (
                account_identifier
                is not None
            ):
                payload[
                    "account_fingerprint"
                ] = (
                    self.account_fingerprint(
                        account_identifier
                    )
                )


            # =================================================
            # FAILURE REASON
            # =================================================


            if (
                reason
                is not None
            ):
                payload[
                    "reason"
                ] = (
                    self._clean_text(
                        reason
                    )
                )


            # =================================================
            # STRUCTURED DETAILS
            # =================================================
            #
            # Every key crosses the sensitive-field classifier
            # before its value can be serialized.
            # =================================================


            if (
                details
            ):
                payload[
                    "details"
                ] = (
                    self._sanitize_details(
                        details
                    )
                )


            # =================================================
            # SERIALIZATION
            # =================================================


            serialized = (
                json.dumps(
                    payload,
                    separators=(
                        ",",
                        ":",
                    ),
                    sort_keys=True,
                )
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

        return (
            hmac.new(
                self._hmac_key,
                message,
                sha256,
            )
            .hexdigest()
        )


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

        if (
            request.client
            is None
        ):
            return (
                "unknown"
            )

        return (
            request.client.host
        )


    # =====================================================
    # STRUCTURED DETAIL SANITIZATION
    # =====================================================


    @classmethod
    def _sanitize_details(
        cls,
        details: SecurityDetails,
    ) -> dict[
        str,
        SecurityDetailValue,
    ]:
        """
        Sanitize one flat structured-details mapping.

        Sensitive fields retain their key so operators can
        still understand which category of information was
        attempted, but the original value is replaced with a
        constant redaction marker.

        Example:

            {
                "refresh_token": "secret",
                "sessions_revoked": 3,
            }

        becomes:

            {
                "refresh_token": "[REDACTED]",
                "sessions_revoked": 3,
            }
        """

        sanitized: dict[
            str,
            SecurityDetailValue,
        ] = {}

        for (
            key,
            value,
        ) in details.items():
            cleaned_key = (
                cls._clean_text(
                    str(
                        key
                    )
                )
            )

            if (
                cls._is_sensitive_detail_key(
                    cleaned_key
                )
            ):
                sanitized[
                    cleaned_key
                ] = (
                    cls
                    .REDACTED_DETAIL_VALUE
                )

                continue

            sanitized[
                cleaned_key
            ] = (
                cls._clean_value(
                    value
                )
            )

        return (
            sanitized
        )


    # =====================================================
    # SENSITIVE DETAIL DETECTION
    # =====================================================


    @classmethod
    def _is_sensitive_detail_key(
        cls,
        key: str,
    ) -> bool:
        """
        Determine whether a structured-detail key represents
        credential-bearing material.

        Key normalization deliberately ignores:

            capitalization
            underscores
            hyphens
            whitespace
            other punctuation

        so naming variations do not bypass the protection.
        """

        normalized_key = (
            cls._normalize_detail_key(
                key
            )
        )

        if (
            not normalized_key
        ):
            return (
                False
            )

        return any(
            marker
            in normalized_key
            for marker
            in (
                cls
                .SENSITIVE_DETAIL_KEY_MARKERS
            )
        )


    # =====================================================
    # DETAIL KEY NORMALIZATION
    # =====================================================


    @staticmethod
    def _normalize_detail_key(
        key: str,
    ) -> str:
        """
        Convert a detail key to a comparison form.

        Examples:

            access_token
                -> accesstoken

            Access-Token
                -> accesstoken

            accessToken
                -> accesstoken

            CLIENT_SECRET
                -> clientsecret
        """

        return (
            "".join(
                character.lower()
                for character
                in key
                if character.isalnum()
            )
        )


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
                " ",
            )
            .replace(
                "\n",
                " ",
            )
            .replace(
                "\t",
                " ",
            )
        )

        return (
            cleaned[
                :max_length
            ]
        )


    @classmethod
    def _clean_value(
        cls,
        value: SecurityDetailValue,
    ) -> SecurityDetailValue:
        """
        Sanitize allowed scalar detail values.

        Numeric, boolean, and None values can pass through
        unchanged.

        String values receive the same control-character and
        size normalization used by other attacker-influenced
        textual fields.
        """

        if isinstance(
            value,
            str,
        ):
            return (
                cls._clean_text(
                    value
                )
            )

        return (
            value
        )


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