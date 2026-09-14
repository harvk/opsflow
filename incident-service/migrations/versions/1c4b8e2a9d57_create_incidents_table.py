"""create independently owned incidents table

Revision ID: 1c4b8e2a9d57
Revises:
Create Date: 2026-09-13

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "1c4b8e2a9d57"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


incident_severity = postgresql.ENUM(
    "SEV-1",
    "SEV-2",
    "SEV-3",
    "SEV-4",
    name="incident_severity",
    create_type=False,
)

incident_status = postgresql.ENUM(
    "Open",
    "Investigating",
    "Monitoring",
    "Resolved",
    name="incident_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()

    incident_severity.create(
        bind,
        checkfirst=True,
    )
    incident_status.create(
        bind,
        checkfirst=True,
    )

    op.create_table(
        "incidents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "service_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.String(length=200),
            nullable=False,
        ),
        sa.Column(
            "severity",
            incident_severity,
            nullable=False,
        ),
        sa.Column(
            "status",
            incident_status,
            nullable=False,
        ),
        sa.Column(
            "summary",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "assignee",
            sa.String(length=120),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.String(length=80),
            server_default=sa.text(
                "'manual'"
            ),
            nullable=False,
        ),
        sa.Column(
            "customer_impacting",
            sa.Boolean(),
            server_default=sa.text(
                "false"
            ),
            nullable=False,
        ),
        sa.Column(
            "acknowledged_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_incidents_assignee",
        "incidents",
        ["assignee"],
        unique=False,
    )
    op.create_index(
        "ix_incidents_created_at",
        "incidents",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_incidents_service_id",
        "incidents",
        ["service_id"],
        unique=False,
    )
    op.create_index(
        "ix_incidents_service_status",
        "incidents",
        [
            "service_id",
            "status",
        ],
        unique=False,
    )
    op.create_index(
        "ix_incidents_severity",
        "incidents",
        ["severity"],
        unique=False,
    )
    op.create_index(
        "ix_incidents_status",
        "incidents",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_incidents_status",
        table_name="incidents",
    )
    op.drop_index(
        "ix_incidents_severity",
        table_name="incidents",
    )
    op.drop_index(
        "ix_incidents_service_status",
        table_name="incidents",
    )
    op.drop_index(
        "ix_incidents_service_id",
        table_name="incidents",
    )
    op.drop_index(
        "ix_incidents_created_at",
        table_name="incidents",
    )
    op.drop_index(
        "ix_incidents_assignee",
        table_name="incidents",
    )

    op.drop_table(
        "incidents"
    )

    bind = op.get_bind()

    incident_status.drop(
        bind,
        checkfirst=True,
    )
    incident_severity.drop(
        bind,
        checkfirst=True,
    )