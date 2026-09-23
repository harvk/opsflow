from sqlalchemy import Enum as SqlEnum
from sqlalchemy import Table

from app.db.base_metadata import Base

INCIDENT_TABLE: Table = Base.metadata.tables[
    "incidents"
]

COMPLETION_OUTBOX_TABLE: Table = Base.metadata.tables[
    "incident_task_completion_outbox"
]


def test_metadata_contains_only_incident_service_tables(
) -> None:
    assert set(
        Base.metadata.tables
    ) == {
        "incidents",
        "incident_task_outbox",
        "incident_task_completion_outbox",
    }


def test_incident_table_contains_expected_columns() -> None:
    assert set(INCIDENT_TABLE.columns.keys()) == {
        "id",
        "service_id",
        "title",
        "severity",
        "status",
        "summary",
        "assignee",
        "source",
        "customer_impacting",
        "acknowledged_at",
        "started_at",
        "resolved_at",
        "created_at",
        "updated_at",
        "reported_by_email",
    }


def test_service_id_is_not_a_database_foreign_key() -> None:
    service_id_column = (
        INCIDENT_TABLE.c.service_id
    )

    assert not service_id_column.foreign_keys
    assert not INCIDENT_TABLE.foreign_keys


def test_incident_table_contains_expected_indexes() -> None:
    index_names = {
        index.name
        for index in INCIDENT_TABLE.indexes
    }

    assert index_names == {
        "ix_incidents_assignee",
        "ix_incidents_created_at",
        "ix_incidents_service_id",
        "ix_incidents_service_status",
        "ix_incidents_severity",
        "ix_incidents_status",
        "ix_incidents_reported_by_email",
    }


def test_incident_enum_storage_uses_public_values() -> None:
    severity_type = (
        INCIDENT_TABLE.c.severity.type
    )
    status_type = (
        INCIDENT_TABLE.c.status.type
    )

    assert isinstance(
        severity_type,
        SqlEnum,
    )
    assert isinstance(
        status_type,
        SqlEnum,
    )

    assert severity_type.enums == [
        "SEV-1",
        "SEV-2",
        "SEV-3",
        "SEV-4",
    ]

    assert status_type.enums == [
        "Open",
        "Investigating",
        "Monitoring",
        "Resolved",
    ]


def test_completion_outbox_contains_expected_columns(
) -> None:
    assert set(
        COMPLETION_OUTBOX_TABLE.columns.keys()
    ) == {
        "id",
        "event_id",
        "incident_id",
        "task_id",
        "correlation_id",
        "schema_version",
        "event_type",
        "status",
        "acknowledged_at",
        "occurred_at",
        "publication_status",
        "publish_attempts",
        "created_at",
        "updated_at",
        "published_at",
        "last_error",
    }


def test_completion_outbox_task_and_event_ids_are_unique(
) -> None:
    assert (
        COMPLETION_OUTBOX_TABLE
        .c
        .task_id
        .unique
        is True
    )

    assert (
        COMPLETION_OUTBOX_TABLE
        .c
        .event_id
        .unique
        is True
    )
