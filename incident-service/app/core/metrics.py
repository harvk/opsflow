from __future__ import annotations

from typing import (
    Final,
)

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)
from prometheus_client.exposition import (
    CONTENT_TYPE_LATEST,
)

PROMETHEUS_CONTENT_TYPE: Final[str] = (
    CONTENT_TYPE_LATEST
)

HTTP_DURATION_BUCKETS: Final[
    tuple[
        float,
        ...,
    ]
] = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)

SERVICE_AUTHENTICATION_OUTCOMES: Final[frozenset[str]] = (
    frozenset({"success", "failure"})
)

SERVICE_AUTHENTICATION_REASONS: Final[frozenset[str]] = (
    frozenset(
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
)

SERVICE_AUTHORIZATION_OUTCOMES: Final[frozenset[str]] = (
    frozenset({"granted", "denied"})
)

SERVICE_AUTHORIZATION_SCOPES: Final[frozenset[str]] = (
    frozenset(
        {
            "incidents:read",
            "incidents:write",
            "services:read",
        }
    )
)


class OperationalMetrics:
    """
    Process-local Prometheus metrics for Incident Management.

    Labels contain only bounded HTTP metadata. Raw identifiers,
    request IDs, credentials, query strings, and exception
    messages are deliberately excluded.
    """

    def __init__(
        self,
    ) -> None:
        self.registry = (
            CollectorRegistry(
                auto_describe=True,
            )
        )

        self._http_requests = Counter(
            (
                "opsflow_http_requests_total"
            ),
            (
                "Completed inbound HTTP requests."
            ),
            (
                "method",
                "route",
                "status_code",
            ),
            registry=self.registry,
        )

        self._http_request_duration = Histogram(
            (
                "opsflow_http_request_duration_seconds"
            ),
            (
                "Inbound HTTP request duration in seconds."
            ),
            (
                "method",
                "route",
            ),
            buckets=HTTP_DURATION_BUCKETS,
            registry=self.registry,
        )

        self._service_authentication_attempts = Counter(
            "opsflow_service_authentication_attempts_total",
            (
                "Completed inbound service-authentication "
                "attempts."
            ),
            ("outcome", "reason"),
            registry=self.registry,
        )

        self._service_authorization_decisions = Counter(
            "opsflow_service_authorization_decisions_total",
            (
                "Completed service-scope authorization "
                "decisions."
            ),
            ("outcome", "scope"),
            registry=self.registry,
        )

    def observe_http_request(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        normalized_method = (
            method.upper()
        )

        self._http_requests.labels(
            method=normalized_method,
            route=route,
            status_code=str(
                status_code
            ),
        ).inc()

        self._http_request_duration.labels(
            method=normalized_method,
            route=route,
        ).observe(
            max(
                duration_seconds,
                0.0,
            )
        )

    def record_service_authentication(
        self,
        *,
        outcome: str,
        reason: str,
    ) -> None:
        if outcome not in SERVICE_AUTHENTICATION_OUTCOMES:
            raise ValueError(
                "Unsupported service-authentication outcome."
            )

        if reason not in SERVICE_AUTHENTICATION_REASONS:
            raise ValueError(
                "Unsupported service-authentication reason."
            )

        self._service_authentication_attempts.labels(
            outcome=outcome,
            reason=reason,
        ).inc()

    def record_service_authorization(
        self,
        *,
        outcome: str,
        scope: str,
    ) -> None:
        if outcome not in SERVICE_AUTHORIZATION_OUTCOMES:
            raise ValueError(
                "Unsupported service-authorization outcome."
            )

        if scope not in SERVICE_AUTHORIZATION_SCOPES:
            raise ValueError(
                "Unsupported service-authorization scope."
            )

        self._service_authorization_decisions.labels(
            outcome=outcome,
            scope=scope,
        ).inc()

    def render(
        self,
    ) -> bytes:
        return generate_latest(
            self.registry
        )


operational_metrics = (
    OperationalMetrics()
)
