from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class IncidentSeverity(str, Enum):
    """
    Supported Incident severity levels.

    The string values form part of the external Incident API
    contract and must remain compatible with the Core Backend.
    """

    SEV_1 = "SEV-1"
    SEV_2 = "SEV-2"
    SEV_3 = "SEV-3"
    SEV_4 = "SEV-4"


class IncidentStatus(str, Enum):
    """
    Supported Incident lifecycle states.

    These values form part of both the API and persistence
    contracts.
    """

    OPEN = "Open"
    INVESTIGATING = "Investigating"
    MONITORING = "Monitoring"
    RESOLVED = "Resolved"


@dataclass(slots=True)
class Incident:
    """
    Persistence-independent Incident domain representation.

    service_id is an external Service Catalog reference. It
    does not imply ownership of a Service record or a database
    foreign-key relationship.
    """

    id: UUID
    title: str
    service_id: UUID
    severity: IncidentSeverity
    status: IncidentStatus
    summary: str
    assignee: str
    started_at: datetime
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    source: str = "manual"
    customer_impacting: bool = False
    acknowledged_at: datetime | None = None
    reported_by_email: str | None = None