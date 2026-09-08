"""rename complete auth session columns

Revision ID: 1538720d1cca
Revises: 7fc26246e0bd
Create Date: 2026-09-06 18:42:54.714434

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "1538720d1cca"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "7fc26246e0bd"

branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None

depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


def upgrade() -> None:
    """
    Rename the existing authentication-session columns to
    match the Phase 6.4C server-side refresh-session model.

    Renaming preserves any existing session data rather than
    dropping the old columns and creating replacements.
    """

    # -----------------------------------------------------
    # current_refresh_jti -> current_jti
    # -----------------------------------------------------

    op.alter_column(
        "auth_sessions",
        "current_refresh_jti",
        new_column_name="current_jti",
        existing_type=postgresql.UUID(
            as_uuid=True
        ),
        existing_nullable=False,
    )

    # -----------------------------------------------------
    # last_refreshed_at -> last_used_at
    # -----------------------------------------------------

    op.alter_column(
        "auth_sessions",
        "last_refreshed_at",
        new_column_name="last_used_at",
        existing_type=postgresql.TIMESTAMP(
            timezone=True
        ),
        existing_nullable=False,
    )

    # -----------------------------------------------------
    # Current refresh-token identifier must be unique
    # -----------------------------------------------------

    op.create_unique_constraint(
        "uq_auth_sessions_current_jti",
        "auth_sessions",
        [
            "current_jti",
        ],
    )


def downgrade() -> None:
    """
    Restore the schema that existed before this revision.
    """

    # -----------------------------------------------------
    # Remove the unique constraint introduced by upgrade()
    # -----------------------------------------------------

    op.drop_constraint(
        "uq_auth_sessions_current_jti",
        "auth_sessions",
        type_="unique",
    )

    # -----------------------------------------------------
    # last_used_at -> last_refreshed_at
    # -----------------------------------------------------

    op.alter_column(
        "auth_sessions",
        "last_used_at",
        new_column_name=(
            "last_refreshed_at"
        ),
        existing_type=postgresql.TIMESTAMP(
            timezone=True
        ),
        existing_nullable=False,
    )

    # -----------------------------------------------------
    # current_jti -> current_refresh_jti
    # -----------------------------------------------------

    op.alter_column(
        "auth_sessions",
        "current_jti",
        new_column_name=(
            "current_refresh_jti"
        ),
        existing_type=postgresql.UUID(
            as_uuid=True
        ),
        existing_nullable=False,
    )