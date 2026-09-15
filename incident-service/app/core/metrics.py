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

    def render(
        self,
    ) -> bytes:
        return generate_latest(
            self.registry
        )


operational_metrics = (
    OperationalMetrics()
)