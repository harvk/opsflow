from __future__ import annotations

from typing import (
    Final,
    Literal,
)

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from prometheus_client.exposition import (
    CONTENT_TYPE_LATEST,
)

PROMETHEUS_CONTENT_TYPE: Final[str] = (
    CONTENT_TYPE_LATEST
)

CircuitMetricState = Literal[
    "closed",
    "open",
    "half_open",
]

CIRCUIT_METRIC_STATES: Final[
    tuple[
        CircuitMetricState,
        ...,
    ]
] = (
    "closed",
    "open",
    "half_open",
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

DEPENDENCY_DURATION_BUCKETS: Final[
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


class OperationalMetrics:
    """
    Process-local Prometheus metrics for the Core Backend.

    Every metric uses a private CollectorRegistry. This avoids
    duplicate-registration errors when test code constructs
    isolated OperationalMetrics objects.

    Labels are deliberately bounded. Raw request paths,
    identifiers, credentials, query strings, and exception
    messages must never become metric labels.
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

        self._dependency_operations = Counter(
            (
                "opsflow_dependency_operations_total"
            ),
            (
                "Completed logical dependency operations."
            ),
            (
                "dependency",
                "method",
                "outcome",
            ),
            registry=self.registry,
        )

        self._dependency_attempts = Counter(
            (
                "opsflow_dependency_attempts_total"
            ),
            (
                "Individual dependency transport attempts."
            ),
            (
                "dependency",
                "method",
                "outcome",
            ),
            registry=self.registry,
        )

        self._dependency_retries = Counter(
            (
                "opsflow_dependency_retries_total"
            ),
            (
                "Dependency retries scheduled after a failed "
                "transport attempt or retryable response."
            ),
            (
                "dependency",
                "method",
                "reason",
            ),
            registry=self.registry,
        )

        self._dependency_operation_duration = Histogram(
            (
                "opsflow_dependency_operation_duration_seconds"
            ),
            (
                "Logical dependency-operation duration, "
                "including retry backoff."
            ),
            (
                "dependency",
                "method",
                "outcome",
            ),
            buckets=DEPENDENCY_DURATION_BUCKETS,
            registry=self.registry,
        )

        self._circuit_breaker_state = Gauge(
            (
                "opsflow_circuit_breaker_state"
            ),
            (
                "One-hot circuit-breaker state."
            ),
            (
                "dependency",
                "state",
            ),
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

        normalized_status = str(
            status_code
        )

        self._http_requests.labels(
            method=normalized_method,
            route=route,
            status_code=normalized_status,
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

    def observe_dependency_operation(
        self,
        *,
        dependency: str,
        method: str,
        outcome: str,
        duration_seconds: float,
    ) -> None:
        normalized_method = (
            method.upper()
        )

        self._dependency_operations.labels(
            dependency=dependency,
            method=normalized_method,
            outcome=outcome,
        ).inc()

        self._dependency_operation_duration.labels(
            dependency=dependency,
            method=normalized_method,
            outcome=outcome,
        ).observe(
            max(
                duration_seconds,
                0.0,
            )
        )

    def record_dependency_attempt(
        self,
        *,
        dependency: str,
        method: str,
        outcome: str,
    ) -> None:
        self._dependency_attempts.labels(
            dependency=dependency,
            method=method.upper(),
            outcome=outcome,
        ).inc()

    def record_dependency_retry(
        self,
        *,
        dependency: str,
        method: str,
        reason: str,
    ) -> None:
        self._dependency_retries.labels(
            dependency=dependency,
            method=method.upper(),
            reason=reason,
        ).inc()

    def set_circuit_state(
        self,
        *,
        dependency: str,
        state: CircuitMetricState,
    ) -> None:
        for candidate_state in (
            CIRCUIT_METRIC_STATES
        ):
            self._circuit_breaker_state.labels(
                dependency=dependency,
                state=candidate_state,
            ).set(
                1.0
                if candidate_state
                == state
                else 0.0
            )

    def render(
        self,
    ) -> bytes:
        return generate_latest(
            self.registry
        )


operational_metrics = (
    OperationalMetrics()
)