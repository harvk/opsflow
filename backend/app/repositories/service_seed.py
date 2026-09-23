from datetime import UTC, datetime, timedelta
from random import Random
from uuid import UUID

from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from app.domain.service import Service, ServiceStatus

SEED_RANDOM_SEED = 20260923
SEED_NOW = datetime(2026, 9, 23, 14, 30, tzinfo=UTC)
DEFAULT_REPORTER_EMAIL = "admin@example.com"

ORDER_API_ID = UUID("11111111-1111-4111-8111-111111111111")
INVENTORY_SYNC_ID = UUID("22222222-2222-4222-8222-222222222222")
NOTIFICATION_WORKER_ID = UUID("33333333-3333-4333-8333-333333333333")
PAYMENT_WEBHOOK_ID = UUID("44444444-4444-4444-8444-444444444444")
AUTH_GATEWAY_ID = UUID("55555555-5555-4555-8555-555555555555")
CUSTOMER_PROFILE_API_ID = UUID("66666666-6666-4666-8666-666666666666")
SEARCH_INDEXER_ID = UUID("77777777-7777-4777-8777-777777777777")
FULFILLMENT_ORCHESTRATOR_ID = UUID("88888888-8888-4888-8888-888888888888")
ANALYTICS_PIPELINE_ID = UUID("99999999-9999-4999-8999-999999999999")


SERVICE_IDS = (
    ORDER_API_ID,
    INVENTORY_SYNC_ID,
    NOTIFICATION_WORKER_ID,
    PAYMENT_WEBHOOK_ID,
    AUTH_GATEWAY_ID,
    CUSTOMER_PROFILE_API_ID,
    SEARCH_INDEXER_ID,
    FULFILLMENT_ORCHESTRATOR_ID,
    ANALYTICS_PIPELINE_ID,
)


def create_seed_services(
    *,
    reported_by_email: str = DEFAULT_REPORTER_EMAIL,
) -> list[Service]:
    """Create nine services with their correlated seed incidents attached.

    The incident records are still independently available through
    create_seed_incidents() for persistence in the Incident Service database.
    Each Service.incidents list contains only incidents whose service_id matches
    that service's id.
    """

    incidents_by_service: dict[UUID, list[Incident]] = {
        service_id: [] for service_id in SERVICE_IDS
    }

    for incident in create_seed_incidents(
        reported_by_email=reported_by_email,
    ):
        incidents_by_service[incident.service_id].append(incident)

    return [
        Service(
            id=ORDER_API_ID,
            name="Order API",
            owner="Commerce Platform",
            status=ServiceStatus.HEALTHY,
            uptime="99.99%",
            latency_ms=42,
            description=(
                "Processes order creation, validation, and lifecycle operations."
            ),
            region="us-east-1",
            version="2.6.0",
            last_deployed_at=datetime(
                2026,
                9,
                22,
                15,
                10,
                tzinfo=UTC,
            ),
            dependencies=[
                "Inventory Sync",
                "Payment Webhook",
                "Auth Gateway",
            ],
            incidents=incidents_by_service[ORDER_API_ID],
        ),
        Service(
            id=INVENTORY_SYNC_ID,
            name="Inventory Sync",
            owner="Supply Chain",
            status=ServiceStatus.DEGRADED,
            uptime="99.72%",
            latency_ms=186,
            description=(
                "Synchronizes inventory quantities and allocation state across "
                "fulfillment systems."
            ),
            region="us-east-1",
            version="1.9.1",
            last_deployed_at=datetime(
                2026,
                9,
                21,
                18,
                15,
                tzinfo=UTC,
            ),
            dependencies=[
                "Fulfillment Orchestrator",
            ],
            incidents=incidents_by_service[INVENTORY_SYNC_ID],
        ),
        Service(
            id=NOTIFICATION_WORKER_ID,
            name="Notification Worker",
            owner="Customer Experience",
            status=ServiceStatus.HEALTHY,
            uptime="99.95%",
            latency_ms=71,
            description=(
                "Processes asynchronous email, SMS, and operational notification "
                "workloads."
            ),
            region="us-west-2",
            version="3.2.0",
            last_deployed_at=datetime(
                2026,
                9,
                20,
                21,
                0,
                tzinfo=UTC,
            ),
            dependencies=[
                "Customer Profile API",
            ],
            incidents=incidents_by_service[NOTIFICATION_WORKER_ID],
        ),
        Service(
            id=PAYMENT_WEBHOOK_ID,
            name="Payment Webhook",
            owner="Payments",
            status=ServiceStatus.CRITICAL,
            uptime="97.84%",
            latency_ms=628,
            description=(
                "Receives and processes asynchronous payment-provider transaction "
                "events."
            ),
            region="us-east-2",
            version="4.1.0",
            last_deployed_at=datetime(
                2026,
                9,
                23,
                12,
                10,
                tzinfo=UTC,
            ),
            dependencies=[
                "Auth Gateway",
            ],
            incidents=incidents_by_service[PAYMENT_WEBHOOK_ID],
        ),
        Service(
            id=AUTH_GATEWAY_ID,
            name="Auth Gateway",
            owner="Identity Platform",
            status=ServiceStatus.HEALTHY,
            uptime="99.997%",
            latency_ms=28,
            description=(
                "Authenticates user and service requests and enforces access-policy "
                "boundaries."
            ),
            region="us-east-1",
            version="5.4.2",
            last_deployed_at=datetime(
                2026,
                9,
                22,
                9,
                45,
                tzinfo=UTC,
            ),
            dependencies=[],
            incidents=incidents_by_service[AUTH_GATEWAY_ID],
        ),
        Service(
            id=CUSTOMER_PROFILE_API_ID,
            name="Customer Profile API",
            owner="Customer Data",
            status=ServiceStatus.HEALTHY,
            uptime="99.96%",
            latency_ms=64,
            description=(
                "Provides customer profile, preferences, and account metadata to "
                "downstream applications."
            ),
            region="us-east-1",
            version="2.2.4",
            last_deployed_at=datetime(
                2026,
                9,
                19,
                16,
                20,
                tzinfo=UTC,
            ),
            dependencies=[
                "Auth Gateway",
            ],
            incidents=incidents_by_service[CUSTOMER_PROFILE_API_ID],
        ),
        Service(
            id=SEARCH_INDEXER_ID,
            name="Search Indexer",
            owner="Discovery Platform",
            status=ServiceStatus.DEGRADED,
            uptime="99.41%",
            latency_ms=247,
            description=(
                "Builds and refreshes searchable indexes from product, inventory, "
                "and customer-facing catalog data."
            ),
            region="us-west-2",
            version="1.6.8",
            last_deployed_at=datetime(
                2026,
                9,
                18,
                11,
                5,
                tzinfo=UTC,
            ),
            dependencies=[
                "Customer Profile API",
            ],
            incidents=incidents_by_service[SEARCH_INDEXER_ID],
        ),
        Service(
            id=FULFILLMENT_ORCHESTRATOR_ID,
            name="Fulfillment Orchestrator",
            owner="Fulfillment Platform",
            status=ServiceStatus.HEALTHY,
            uptime="99.93%",
            latency_ms=92,
            description=(
                "Coordinates fulfillment workflows across inventory, warehouse, "
                "and customer-notification services."
            ),
            region="us-east-1",
            version="3.7.3",
            last_deployed_at=datetime(
                2026,
                9,
                21,
                7,
                40,
                tzinfo=UTC,
            ),
            dependencies=[
                "Inventory Sync",
                "Notification Worker",
            ],
            incidents=incidents_by_service[FULFILLMENT_ORCHESTRATOR_ID],
        ),
        Service(
            id=ANALYTICS_PIPELINE_ID,
            name="Analytics Pipeline",
            owner="Data Platform",
            status=ServiceStatus.HEALTHY,
            uptime="99.88%",
            latency_ms=134,
            description=(
                "Processes operational events into near-real-time analytics and "
                "platform-health datasets."
            ),
            region="us-east-2",
            version="6.0.1",
            last_deployed_at=datetime(
                2026,
                9,
                20,
                5,
                55,
                tzinfo=UTC,
            ),
            dependencies=[
                "Order API",
                "Inventory Sync",
            ],
            incidents=incidents_by_service[ANALYTICS_PIPELINE_ID],
        ),
    ]


def create_seed_incidents(
    *,
    reported_by_email: str = DEFAULT_REPORTER_EMAIL,
) -> list[Incident]:
    """Create reproducible incident data across four pseudo-random services.

    This factory is independent of create_seed_services() so the service
    factory can safely attach the resulting incidents without recursion.

    A fixed RNG seed keeps local development and portfolio environments
    deterministic while still distributing incidents across a sample of four
    services. Incident fields mirror the current Incident persistence model,
    including source, customer impact, acknowledgement, and reporter email.
    """

    incident_service_ids = Random(SEED_RANDOM_SEED).sample(
        list(SERVICE_IDS),
        k=4,
    )

    (
        customer_profile_id,
        payment_webhook_id,
        notification_worker_id,
        search_indexer_id,
    ) = incident_service_ids

    return [
        Incident(
            id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
            title="Customer profile lookups returning elevated 5xx responses",
            service_id=customer_profile_id,
            severity=IncidentSeverity.SEV_2,
            status=IncidentStatus.INVESTIGATING,
            summary=(
                "A subset of customer profile requests are returning server errors "
                "while the data team investigates a downstream connection-pool "
                "saturation condition."
            ),
            assignee="Customer Data On-Call",
            source="seed",
            customer_impacting=True,
            acknowledged_at=SEED_NOW - timedelta(minutes=37),
            reported_by_email=reported_by_email,
            started_at=SEED_NOW - timedelta(minutes=44),
            resolved_at=None,
            created_at=SEED_NOW - timedelta(minutes=42),
            updated_at=SEED_NOW - timedelta(minutes=8),
        ),
        Incident(
            id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
            title="Payment callback retry backlog",
            service_id=payment_webhook_id,
            severity=IncidentSeverity.SEV_1,
            status=IncidentStatus.MONITORING,
            summary=(
                "Payment-provider callbacks accumulated in the retry queue after "
                "intermittent downstream processing failures. Recovery is in "
                "progress and backlog depth is decreasing."
            ),
            assignee="Payments Reliability",
            source="seed",
            customer_impacting=True,
            acknowledged_at=SEED_NOW - timedelta(hours=1, minutes=8),
            reported_by_email=reported_by_email,
            started_at=SEED_NOW - timedelta(hours=1, minutes=19),
            resolved_at=None,
            created_at=SEED_NOW - timedelta(hours=1, minutes=16),
            updated_at=SEED_NOW - timedelta(minutes=12),
        ),
        Incident(
            id=UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
            title="Notification delivery queue latency",
            service_id=notification_worker_id,
            severity=IncidentSeverity.SEV_3,
            status=IncidentStatus.RESOLVED,
            summary=(
                "Outbound notification jobs experienced elevated queue latency "
                "during a short-lived traffic spike. Worker capacity was scaled "
                "and the queue returned to normal."
            ),
            assignee="Customer Experience Platform",
            source="seed",
            customer_impacting=False,
            acknowledged_at=SEED_NOW - timedelta(hours=3, minutes=2),
            reported_by_email=reported_by_email,
            started_at=SEED_NOW - timedelta(hours=3, minutes=14),
            resolved_at=SEED_NOW - timedelta(hours=2, minutes=26),
            created_at=SEED_NOW - timedelta(hours=3, minutes=11),
            updated_at=SEED_NOW - timedelta(hours=2, minutes=26),
        ),
        Incident(
            id=UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"),
            title="Search indexing lag above operating threshold",
            service_id=search_indexer_id,
            severity=IncidentSeverity.SEV_2,
            status=IncidentStatus.OPEN,
            summary=(
                "Catalog changes are taking longer than expected to appear in the "
                "search index. Query availability remains intact while indexing "
                "throughput is being restored."
            ),
            assignee="Discovery Platform",
            source="seed",
            customer_impacting=False,
            acknowledged_at=None,
            reported_by_email=reported_by_email,
            started_at=SEED_NOW - timedelta(minutes=24),
            resolved_at=None,
            created_at=SEED_NOW - timedelta(minutes=22),
            updated_at=SEED_NOW - timedelta(minutes=4),
        ),
        Incident(
            id=UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"),
            title="Payment webhook signature verification errors",
            service_id=payment_webhook_id,
            severity=IncidentSeverity.SEV_2,
            status=IncidentStatus.RESOLVED,
            summary=(
                "A configuration mismatch caused a portion of payment webhook "
                "signatures to fail verification. The signing configuration was "
                "corrected and queued callbacks were replayed."
            ),
            assignee="Payments Reliability",
            source="seed",
            customer_impacting=True,
            acknowledged_at=SEED_NOW - timedelta(days=1, hours=2, minutes=6),
            reported_by_email=reported_by_email,
            started_at=SEED_NOW - timedelta(days=1, hours=2, minutes=15),
            resolved_at=SEED_NOW - timedelta(days=1, hours=1, minutes=22),
            created_at=SEED_NOW - timedelta(days=1, hours=2, minutes=12),
            updated_at=SEED_NOW - timedelta(days=1, hours=1, minutes=22),
        ),
        Incident(
            id=UUID("ffffffff-ffff-4fff-8fff-ffffffffffff"),
            title="Search refresh worker memory pressure",
            service_id=search_indexer_id,
            severity=IncidentSeverity.SEV_3,
            status=IncidentStatus.RESOLVED,
            summary=(
                "A search refresh worker exceeded its memory target during a large "
                "catalog update. The worker was recycled and batch sizing was "
                "reduced."
            ),
            assignee="Discovery Platform",
            source="seed",
            customer_impacting=False,
            acknowledged_at=SEED_NOW - timedelta(days=2, hours=4, minutes=34),
            reported_by_email=reported_by_email,
            started_at=SEED_NOW - timedelta(days=2, hours=4, minutes=40),
            resolved_at=SEED_NOW - timedelta(days=2, hours=3, minutes=51),
            created_at=SEED_NOW - timedelta(days=2, hours=4, minutes=38),
            updated_at=SEED_NOW - timedelta(days=2, hours=3, minutes=51),
        ),
    ]
