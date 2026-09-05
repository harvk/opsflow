from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class ServiceStatus(str, Enum):
    HEALTHY = "Healthy"
    DEGRADED = "Degraded"
    CRITICAL = "Critical"


@dataclass(slots=True)
class Service:
    id: UUID
    name: str
    owner: str
    status: ServiceStatus
    uptime: str
    latency_ms: int
    description: str
    region: str
    version: str
    last_deployed_at: datetime
    dependencies: list[str]
