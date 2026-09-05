from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class IncidentSeverity(str, Enum):
    SEV_1 = "SEV-1"
    SEV_2 = "SEV-2"
    SEV_3 = "SEV-3"
    SEV_4 = "SEV-4"


class IncidentStatus(str, Enum):
    OPEN = "Open"
    INVESTIGATING = "Investigating"
    MONITORING = "Monitoring"
    RESOLVED = "Resolved"


@dataclass(slots=True)
class Incident:
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
