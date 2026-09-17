from __future__ import annotations

import json
import logging
from datetime import (
    UTC,
    datetime,
    timedelta,
)
from unittest.mock import (
    Mock,
)
from uuid import (
    uuid4,
)

import pytest
from fastapi import (
    HTTPException,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
)

from app.api import (
    dependencies,
)
from app.core.request_context import (
    bind_request_id,
    reset_request_id,
)
from app.core.service_identity import (
    ServiceScope,
)
from app.core.service_security_events import (
    ServiceSecurityEventLogger,
)
from app.core.service_token_verifier import (
    ServiceAuthenticationError,
    ServiceAuthenticationFailureReason,
    ServicePrincipal,
)


class RejectingVerifier:
    def verify_token(
        self,
        token: str,
    ) -> ServicePrincipal:
        raise ServiceAuthenticationError(
            reason=(
                ServiceAuthenticationFailureReason
                .UNKNOWN_KEY
            )
        )


class RecordingServiceSecurityEventLogger:
    def __init__(
        self,
    ) -> None:
        self.authentication_events: list[
            tuple[str, str]
        ] = []
        self.authorization_events: list[
            tuple[str, str]
        ] = []

    def emit_authentication(
        self,
        *,
        outcome: str,
        reason: str,
    ) -> None:
        self.authentication_events.append(
            (
                outcome,
                reason,
            )
        )

    def emit_authorization(
        self,
        *,
        outcome: str,
        scope: str,
    ) -> None:
        self.authorization_events.append(
            (
                outcome,
                scope,
            )
        )


def build_principal(
    *,
    scopes: frozenset[ServiceScope],
) -> ServicePrincipal:
    issued_at = datetime(
        2026,
        9,
        17,
        12,
        0,
        tzinfo=UTC,
    )

    return ServicePrincipal(
        issuer="opsflow-incident-service",
        subject="opsflow-incident-service",
        audience="opsflow-core-backend",
        token_id=uuid4(),
        issued_at=issued_at,
        not_before=issued_at,
        expires_at=(
            issued_at
            + timedelta(
                seconds=60
            )
        ),
        scopes=scopes,
    )


def test_service_security_event_is_structured_and_correlated(
) -> None:
    logger = Mock(
        spec=logging.Logger
    )
    event_logger = ServiceSecurityEventLogger(
        logger=logger
    )
    request_id = (
        "123e4567-e89b-42d3-a456-426614174000"
    )
    context_token = bind_request_id(
        request_id
    )

    try:
        event_logger.emit_authentication(
            outcome="failure",
            reason="invalid_signature",
        )
    finally:
        reset_request_id(
            context_token
        )

    serialized = logger.log.call_args.args[1]
    payload = json.loads(
        serialized
    )

    assert payload[
        "event"
    ] == "service_authentication"
    assert payload[
        "outcome"
    ] == "failure"
    assert payload[
        "reason"
    ] == "invalid_signature"
    assert payload[
        "request_id"
    ] == request_id
    assert "token" not in payload
    assert "credential" not in payload
    assert "claims" not in payload


def test_service_security_event_rejects_unbounded_values(
) -> None:
    event_logger = ServiceSecurityEventLogger(
        logger=Mock(
            spec=logging.Logger
        )
    )

    with pytest.raises(
        ValueError,
        match="authentication event reason",
    ):
        event_logger.emit_authentication(
            outcome="failure",
            reason="attacker-controlled-value",
        )

    with pytest.raises(
        ValueError,
        match="authorization event scope",
    ):
        event_logger.emit_authorization(
            outcome="blocked",
            scope="services:delete",
        )


def test_logging_sink_failure_does_not_escape(
) -> None:
    logger = Mock(
        spec=logging.Logger
    )
    logger.log.side_effect = RuntimeError(
        "logging unavailable"
    )
    event_logger = ServiceSecurityEventLogger(
        logger=logger
    )

    event_logger.emit_authentication(
        outcome="failure",
        reason="unknown_key",
    )


def test_dependencies_emit_rejection_and_scope_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = (
        RecordingServiceSecurityEventLogger()
    )
    monkeypatch.setattr(
        dependencies,
        "service_security_event_logger",
        recorder,
    )

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="opaque-test-credential",
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        dependencies.authenticate_incident_service(
            credentials,
            RejectingVerifier(),
        )

    assert exc_info.value.status_code == 401
    assert recorder.authentication_events == [
        (
            "failure",
            "unknown_key",
        )
    ]

    principal = build_principal(
        scopes=frozenset()
    )

    with pytest.raises(
        HTTPException
    ) as scope_exc_info:
        dependencies.require_services_read(
            principal
        )

    assert scope_exc_info.value.status_code == 403
    assert recorder.authorization_events == [
        (
            "blocked",
            "services:read",
        )
    ]
