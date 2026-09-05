from datetime import UTC, datetime
from uuid import UUID

from app.domain.service import Service, ServiceStatus


def create_seed_services() -> list[Service]:
    return [
        Service(
            id=UUID("11111111-1111-4111-8111-111111111111"),
            name="Order API",
            owner="Commerce Platform",
            status=ServiceStatus.HEALTHY,
            uptime="99.99%",
            latency_ms=42,
            description=("Processes order creation and order lifecycle operations."),
            region="us-east-1",
            version="2.4.1",
            last_deployed_at=datetime(
                2026,
                9,
                3,
                14,
                30,
                tzinfo=UTC,
            ),
            dependencies=[
                "Inventory Sync",
                "Payment Webhook",
            ],
            incidents=[]
        ),
        Service(
            id=UUID("22222222-2222-4222-8222-222222222222"),
            name="Inventory Sync",
            owner="Supply Chain",
            status=ServiceStatus.DEGRADED,
            uptime="99.72%",
            latency_ms=186,
            description=("Synchronizes inventory quantities across fulfillment systems."),
            region="us-east-1",
            version="1.8.3",
            last_deployed_at=datetime(
                2026,
                9,
                2,
                18,
                15,
                tzinfo=UTC,
            ),
            dependencies=[],
            incidents=[]
        ),
        Service(
            id=UUID("33333333-3333-4333-8333-333333333333"),
            name="Notification Worker",
            owner="Customer Experience",
            status=ServiceStatus.HEALTHY,
            uptime="99.95%",
            latency_ms=71,
            description=("Processes asynchronous email and notification workloads."),
            region="us-west-2",
            version="3.1.0",
            last_deployed_at=datetime(
                2026,
                8,
                31,
                21,
                0,
                tzinfo=UTC,
            ),
            dependencies=[
                "Order API",
            ],
            incidents=[]
        ),
        Service(
            id=UUID("44444444-4444-4444-8444-444444444444"),
            name="Payment Webhook",
            owner="Payments",
            status=ServiceStatus.CRITICAL,
            uptime="97.84%",
            latency_ms=628,
            description=("Receives and processes asynchronous payment provider events."),
            region="us-east-2",
            version="4.0.2",
            last_deployed_at=datetime(
                2026,
                9,
                4,
                12,
                10,
                tzinfo=UTC,
            ),
            dependencies=[],
            incidents=[]
        ),
    ]
