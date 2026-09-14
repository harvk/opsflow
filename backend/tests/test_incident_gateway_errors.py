import pytest
from fastapi import status

from app.api.incident_gateway_errors import (
    incident_gateway_http_exception,
)
from app.gateways.incident_gateway import (
    IncidentGatewayError,
    IncidentGatewayProtocolError,
    IncidentGatewayUnavailableError,
)


@pytest.mark.parametrize(
    (
        "gateway_error",
        "expected_status",
        "expected_detail",
    ),
    [
        (
            IncidentGatewayUnavailableError(
                "internal transport detail"
            ),
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Incident service is unavailable.",
        ),
        (
            IncidentGatewayProtocolError(
                "internal protocol detail"
            ),
            status.HTTP_502_BAD_GATEWAY,
            (
                "Incident service returned "
                "an invalid response."
            ),
        ),
    ],
)
def test_incident_gateway_error_translation(
    gateway_error: IncidentGatewayError,
    expected_status: int,
    expected_detail: str,
) -> None:
    http_error = (
        incident_gateway_http_exception(
            gateway_error
        )
    )

    assert (
        http_error.status_code
        == expected_status
    )

    assert (
        http_error.detail
        == expected_detail
    )

    assert (
        "internal"
        not in str(
            http_error.detail
        ).lower()
    )