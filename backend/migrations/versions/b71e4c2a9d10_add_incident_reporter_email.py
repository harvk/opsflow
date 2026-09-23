"""add incident reporter email

Revision ID: b71e4c2a9d10
Revises: 954a9e3b2f31
Create Date: 2026-09-23 09:15:00
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "b71e4c2a9d10"
down_revision: str | Sequence[str] | None = "954a9e3b2f31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column(
            "reported_by_email",
            sa.String(length=320),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_incidents_reported_by_email",
        "incidents",
        ["reported_by_email"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_incidents_reported_by_email",
        table_name="incidents",
    )
    op.drop_column(
        "incidents",
        "reported_by_email",
    )
