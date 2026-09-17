from __future__ import annotations

import json
import logging
from datetime import (
    UTC,
    datetime,
)
from typing import (
    Final,
)
from uuid import (
    uuid4,
)

from app.core.request_context import (
    get_request_id,
)

SERVICE_SECURITY_EVENTS: Final[frozenset[str]] = frozenset(
    {
        "service_authentication",
        "service_authorization",
    }
)

SERVICE_SECURITY_OUTCOMES: Final[frozenset[str]] = frozenset(
    {
        "success",
        "failure",
        "blocked",
    }
)

SERVICE_AUTHENTICATION_REASONS: Final[frozenset[str]] = frozenset(
    {
        "authenticated",
        "missing_credential",
        "malformed_credential",
        "invalid_algorithm",
        "invalid_token_type",
        "missing_key_id",
        "unknown_key",
        "invalid_signature",
        "invalid_issuer",
        "invalid_audience",
        "invalid_claim_contract",
        "invalid_token_use",
        "invalid_lifetime",
        "invalid_scope_contract",
    }
)

SERVICE_AUTHORIZATION_SCOPES: Final[frozenset[str]] = frozenset(
    {
        "incidents:read",
        "incidents:write",
        "services:read",
    }
)


class ServiceSecurityEventLogger:
    """
    Emit bounded service-authentication security events.

    The API accepts only fixed, low-cardinality values. It does
    not accept credentials, JWT claims, key identifiers,
    exception messages, or request objects.
    """

    LOGGER_NAME = "opsflow.service_security"

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = (
            logger
            if logger is not None
            else logging.getLogger(
                self.LOGGER_NAME
            )
        )
        self._logger.setLevel(
            logging.INFO
        )

    def emit_authentication(
        self,
        *,
        outcome: str,
        reason: str,
    ) -> None:
        if outcome not in {
            "success",
            "failure",
        }:
            raise ValueError(
                "Unsupported authentication event outcome."
            )

        if reason not in SERVICE_AUTHENTICATION_REASONS:
            raise ValueError(
                "Unsupported authentication event reason."
            )

        self._emit(
            event="service_authentication",
            outcome=outcome,
            reason=reason,
        )

    def emit_authorization(
        self,
        *,
        outcome: str,
        scope: str,
    ) -> None:
        if outcome not in {
            "success",
            "blocked",
        }:
            raise ValueError(
                "Unsupported authorization event outcome."
            )

        if scope not in SERVICE_AUTHORIZATION_SCOPES:
            raise ValueError(
                "Unsupported authorization event scope."
            )

        self._emit(
            event="service_authorization",
            outcome=outcome,
            scope=scope,
        )

    def _emit(
        self,
        *,
        event: str,
        outcome: str,
        reason: str | None = None,
        scope: str | None = None,
    ) -> None:
        if event not in SERVICE_SECURITY_EVENTS:
            raise ValueError(
                "Unsupported service security event."
            )

        if outcome not in SERVICE_SECURITY_OUTCOMES:
            raise ValueError(
                "Unsupported service security outcome."
            )

        try:
            payload: dict[str, str] = {
                "event_id": str(
                    uuid4()
                ),
                "occurred_at": datetime.now(
                    UTC
                ).isoformat(),
                "event": event,
                "outcome": outcome,
            }

            request_id = get_request_id()

            if request_id is not None:
                payload[
                    "request_id"
                ] = request_id

            if reason is not None:
                payload[
                    "reason"
                ] = reason

            if scope is not None:
                payload[
                    "scope"
                ] = scope

            level = (
                logging.INFO
                if outcome == "success"
                else logging.WARNING
            )

            self._logger.log(
                level,
                json.dumps(
                    payload,
                    separators=(
                        ",",
                        ":",
                    ),
                    sort_keys=True,
                ),
            )

        except Exception:  # noqa: BLE001
            return


service_security_event_logger = (
    ServiceSecurityEventLogger()
)
