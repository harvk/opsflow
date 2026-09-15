from fastapi import (
    HTTPException,
    status,
)

from app.gateways.incident_gateway import (
    IncidentGatewayCircuitOpenError,
    IncidentGatewayError,
    IncidentGatewayUnavailableError,
)


def incident_gateway_http_exception(
    error: IncidentGatewayError,
) -> HTTPException:
    """
    Translate internal IncidentGateway failures into stable,
    non-sensitive public HTTP responses.

    A circuit-open response includes a bounded Retry-After
    header so callers know when a probe may be permitted.
    Internal breaker or transport details remain private.
    """

    if isinstance(
        error,
        IncidentGatewayCircuitOpenError,
    ):
        return HTTPException(
            status_code=(
                status
                .HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Incident service is unavailable."
            ),
            headers={
                "Retry-After": str(
                    error
                    .retry_after_seconds
                )
            },
        )

    if isinstance(
        error,
        IncidentGatewayUnavailableError,
    ):
        return HTTPException(
            status_code=(
                status
                .HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Incident service is unavailable."
            ),
        )

    return HTTPException(
        status_code=(
            status
            .HTTP_502_BAD_GATEWAY
        ),
        detail=(
            "Incident service returned "
            "an invalid response."
        ),
    )