from datetime import datetime, timezone
from uuid import UUID

from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from app.domain.service import (
    Service,
    ServiceStatus,
)


PAYMENTS_SERVICE_ID = UUID(
    "11111111-1111-1111-1111-111111111111"
)

IDENTITY_SERVICE_ID = UUID(
    "22222222-2222-2222-2222-222222222222"
)

PAYMENTS_INCIDENT_ID = UUID(
    "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
)

def create_seed_services() -> list[Service]:
    now = datetime.now(timezone.utc)

    return [
        Service(
            id=PAYMENTS_SERVICE_ID,
            name="Payments API",
            owner="Payments Team",
            status=ServiceStatus.HEALTHY,
            uptime="99.99%",
            latency_ms=42,
            description="Processes customer payments.",
            region="us-east-1",
            version="2.4.1",
            last_deployed_at=now,
            dependencies=[
                "Identity API",
                "PostgreSQL",
            ],
            incidents=[],
        ),
        Service(
            id=IDENTITY_SERVICE_ID,
            name="Identity API",
            owner="Platform Team",
            status=ServiceStatus.HEALTHY,
            uptime="99.98%",
            latency_ms=31,
            description="Provides identity services.",
            region="us-east-1",
            version="3.1.0",
            last_deployed_at=now,
            dependencies=[
                "PostgreSQL",
            ],
            incidents=[]
        ),
    ]
    
def create_seed_incidents() -> list[Incident]:
    now = datetime.now(timezone.utc)

    return [
        Incident(
            id=PAYMENTS_INCIDENT_ID,
            title="Elevated payment latency",
            service_id=PAYMENTS_SERVICE_ID,
            severity=IncidentSeverity.SEV_2,
            status=IncidentStatus.INVESTIGATING,
            summary=(
                "Payment latency exceeded "
                "the expected threshold."
            ),
            assignee="Payments Team",
            started_at=now,
            resolved_at=None,
            created_at=now,
            updated_at=now,
        ),
    ]