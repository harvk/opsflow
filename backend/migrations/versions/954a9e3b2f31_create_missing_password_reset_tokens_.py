"""create missing password reset tokens table

Revision ID: 954a9e3b2f31
Revises: a5b1c6285b42
Create Date: 2026-09-07 02:24:29.186493
"""

from typing import (
    Sequence,
    Union,
)

from alembic import (
    op,
)

import sqlalchemy as sa

from sqlalchemy.dialects import (
    postgresql,
)


# =========================================================
# ALEMBIC REVISION IDENTIFIERS
# =========================================================

revision: str = (
    "954a9e3b2f31"
)

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "a5b1c6285b42"

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


# =========================================================
# UPGRADE
# =========================================================


def upgrade() -> None:
    """
    Create persistent password-reset credential storage.

    The raw password-reset bearer token is never stored.

    token_digest contains the SHA-256 digest used for secure
    lookup.

    credential_fingerprint binds the reset credential to the
    password hash/version that existed when the reset request
    was created.
    """

    # =====================================================
    # PASSWORD RESET TOKENS TABLE
    # =====================================================

    op.create_table(
        "password_reset_tokens",

        # -------------------------------------------------
        # PRIMARY KEY
        # -------------------------------------------------

        sa.Column(
            "id",
            postgresql.UUID(
                as_uuid=True
            ),
            nullable=False,
        ),

        # -------------------------------------------------
        # USER RELATIONSHIP
        # -------------------------------------------------

        sa.Column(
            "user_id",
            postgresql.UUID(
                as_uuid=True
            ),
            nullable=False,
        ),

        # -------------------------------------------------
        # RESET CREDENTIAL
        # -------------------------------------------------

        sa.Column(
            "token_digest",
            sa.String(
                length=64
            ),
            nullable=False,
        ),

        sa.Column(
            "credential_fingerprint",
            sa.String(
                length=64
            ),
            nullable=False,
        ),

        # -------------------------------------------------
        # LIFECYCLE TIMESTAMPS
        # -------------------------------------------------

        sa.Column(
            "created_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=False,
        ),

        sa.Column(
            "expires_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=False,
        ),

        sa.Column(
            "used_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=True,
        ),

        sa.Column(
            "invalidated_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=True,
        ),

        # -------------------------------------------------
        # FOREIGN KEY
        # -------------------------------------------------

        sa.ForeignKeyConstraint(
            [
                "user_id",
            ],
            [
                "users.id",
            ],
            ondelete="CASCADE",
        ),

        # -------------------------------------------------
        # PRIMARY KEY CONSTRAINT
        # -------------------------------------------------

        sa.PrimaryKeyConstraint(
            "id"
        ),

        # -------------------------------------------------
        # TOKEN DIGEST MUST BE UNIQUE
        # -------------------------------------------------

        sa.UniqueConstraint(
            "token_digest",
            name=(
                "uq_password_reset_tokens_"
                "token_digest"
            ),
        ),
    )

    # =====================================================
    # USER LOOKUP INDEX
    # =====================================================

    op.create_index(
        "ix_password_reset_tokens_user_id",
        "password_reset_tokens",
        [
            "user_id",
        ],
        unique=False,
    )

    # =====================================================
    # EXPIRATION / MAINTENANCE INDEX
    # =====================================================

    op.create_index(
        "ix_password_reset_tokens_expires_at",
        "password_reset_tokens",
        [
            "expires_at",
        ],
        unique=False,
    )


# =========================================================
# DOWNGRADE
# =========================================================


def downgrade() -> None:
    """
    Remove password-reset credential persistence.
    """

    # Drop indexes explicitly before removing the table.

    op.drop_index(
        "ix_password_reset_tokens_expires_at",
        table_name=(
            "password_reset_tokens"
        ),
    )

    op.drop_index(
        "ix_password_reset_tokens_user_id",
        table_name=(
            "password_reset_tokens"
        ),
    )

    op.drop_table(
        "password_reset_tokens"
    )