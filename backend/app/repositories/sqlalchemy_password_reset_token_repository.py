from __future__ import annotations

from datetime import datetime

from typing import (
    Any,
    cast,
)

from uuid import UUID

from sqlalchemy import (
    select,
    update,
)

from sqlalchemy.engine import (
    CursorResult,
)

from sqlalchemy.orm import (
    Session,
)

from app.domain.password_reset_token import (
    PasswordResetToken,
)

from app.models.password_reset_token import (
    PasswordResetTokenModel,
)

from app.repositories.password_reset_token_repository import (
    PasswordResetTokenRepository,
)


class SqlAlchemyPasswordResetTokenRepository(
    PasswordResetTokenRepository
):
    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = (
            session
        )

    # =====================================================
    # CREATE
    # =====================================================

    def create(
        self,
        reset_token: PasswordResetToken,
    ) -> PasswordResetToken:
        model = PasswordResetTokenModel(
            id=(
                reset_token.id
            ),
            user_id=(
                reset_token.user_id
            ),
            token_digest=(
                reset_token.token_digest
            ),
            credential_fingerprint=(
                reset_token
                .credential_fingerprint
            ),
            created_at=(
                reset_token.created_at
            ),
            expires_at=(
                reset_token.expires_at
            ),
            used_at=(
                reset_token.used_at
            ),
            invalidated_at=(
                reset_token.invalidated_at
            ),
        )

        self.session.add(
            model
        )

        self.session.flush()

        return self._to_domain(
            model
        )

    # =====================================================
    # READ
    # =====================================================

    def get_by_id(
        self,
        token_id: UUID,
    ) -> PasswordResetToken | None:
        statement = (
            select(
                PasswordResetTokenModel
            )
            .where(
                PasswordResetTokenModel.id
                == token_id
            )
        )

        model = (
            self.session
            .execute(
                statement
            )
            .scalar_one_or_none()
        )

        if model is None:
            return None

        return self._to_domain(
            model
        )

    def get_by_digest_for_update(
        self,
        token_digest: str,
    ) -> PasswordResetToken | None:
        """
        Acquire a row-level PostgreSQL lock before token
        consumption.

        The lock is held until the surrounding SQLAlchemy
        transaction commits or rolls back.
        """

        statement = (
            select(
                PasswordResetTokenModel
            )
            .where(
                PasswordResetTokenModel
                .token_digest
                == token_digest
            )
            .with_for_update()
        )

        model = (
            self.session
            .execute(
                statement
            )
            .scalar_one_or_none()
        )

        if model is None:
            return None

        return self._to_domain(
            model
        )

    # =====================================================
    # CONSUMPTION
    # =====================================================

    def mark_used(
        self,
        *,
        token_id: UUID,
        used_at: datetime,
    ) -> bool:
        """
        Consume the token only if it has not already been
        used or invalidated.
        """

        statement = (
            update(
                PasswordResetTokenModel
            )
            .where(
                PasswordResetTokenModel.id
                == token_id
            )
            .where(
                PasswordResetTokenModel.used_at
                .is_(None)
            )
            .where(
                PasswordResetTokenModel
                .invalidated_at
                .is_(None)
            )
            .values(
                used_at=(
                    used_at
                )
            )
        )

        result = cast(
            CursorResult[Any],
            self.session.execute(
                statement
            ),
        )

        self.session.flush()

        return (
            result.rowcount
            == 1
        )

    # =====================================================
    # INVALIDATION
    # =====================================================

    def invalidate_active_for_user(
        self,
        *,
        user_id: UUID,
        invalidated_at: datetime,
        exclude_token_id: UUID | None = None,
    ) -> int:
        statement = (
            update(
                PasswordResetTokenModel
            )
            .where(
                PasswordResetTokenModel.user_id
                == user_id
            )
            .where(
                PasswordResetTokenModel.used_at
                .is_(None)
            )
            .where(
                PasswordResetTokenModel
                .invalidated_at
                .is_(None)
            )
        )

        if (
            exclude_token_id
            is not None
        ):
            statement = (
                statement.where(
                    PasswordResetTokenModel.id
                    != exclude_token_id
                )
            )

        statement = (
            statement.values(
                invalidated_at=(
                    invalidated_at
                )
            )
        )

        result = cast(
            CursorResult[Any],
            self.session.execute(
                statement
            ),
        )

        self.session.flush()

        if (
            result.rowcount
            < 0
        ):
            return 0

        return result.rowcount

    # =====================================================
    # MAPPING
    # =====================================================

    @staticmethod
    def _to_domain(
        model: PasswordResetTokenModel,
    ) -> PasswordResetToken:
        return PasswordResetToken(
            id=(
                model.id
            ),
            user_id=(
                model.user_id
            ),
            token_digest=(
                model.token_digest
            ),
            credential_fingerprint=(
                model
                .credential_fingerprint
            ),
            created_at=(
                model.created_at
            ),
            expires_at=(
                model.expires_at
            ),
            used_at=(
                model.used_at
            ),
            invalidated_at=(
                model.invalidated_at
            ),
        )