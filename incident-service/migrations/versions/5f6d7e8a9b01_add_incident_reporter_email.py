"""add incident reporter email

Revision ID: 5f6d7e8a9b01
Revises: 1b4f045e1eca
Create Date: 2026-09-23 09:15:00
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "5f6d7e8a9b01"
down_revision: str | Sequence[str] | None = "1b4f045e1eca"
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
