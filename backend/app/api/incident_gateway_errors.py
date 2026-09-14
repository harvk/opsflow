from fastapi import HTTPException, status

from app.gateways.incident_gateway import (
    IncidentGatewayError,
    IncidentGatewayUnavailableError,
)


def incident_gateway_http_exception(
    error: IncidentGatewayError,
) -> HTTPException:
    """
    Translate internal IncidentGateway failures into stable,
    non-sensitive public HTTP responses.
    """

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