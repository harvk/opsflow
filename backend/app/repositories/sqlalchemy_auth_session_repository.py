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

from app.domain.auth_session import (
    AuthSession,
)

from app.models.auth_session import (
    AuthSessionModel,
)

from app.repositories.auth_session_repository import (
    AuthSessionRepository,
)


class SqlAlchemyAuthSessionRepository(
    AuthSessionRepository
):
    """
    SQLAlchemy/PostgreSQL implementation of the
    AuthSessionRepository contract.

    Repository methods deliberately flush rather than commit.

    Transaction ownership remains outside the repository so
    later refresh-token rotation and reuse-detection logic can
    control commit/rollback behavior explicitly.
    """

    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    # =====================================================
    # CREATE
    # =====================================================

    def create(
        self,
        auth_session: AuthSession,
    ) -> AuthSession:
        model = AuthSessionModel(
            id=(
                auth_session.id
            ),
            user_id=(
                auth_session.user_id
            ),
            current_jti=(
                auth_session.current_jti
            ),
            created_at=(
                auth_session.created_at
            ),
            last_used_at=(
                auth_session.last_used_at
            ),
            expires_at=(
                auth_session.expires_at
            ),
            revoked_at=(
                auth_session.revoked_at
            ),
            revocation_reason=(
                auth_session
                .revocation_reason
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
        session_id: UUID,
    ) -> AuthSession | None:
        statement = (
            select(
                AuthSessionModel
            )
            .where(
                AuthSessionModel.id
                == session_id
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

    def get_by_id_for_update(
        self,
        session_id: UUID,
    ) -> AuthSession | None:
        statement = (
            select(
                AuthSessionModel
            )
            .where(
                AuthSessionModel.id
                == session_id
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
    # ROTATION
    # =====================================================

    def update_current_token(
        self,
        *,
        session_id: UUID,
        current_jti: UUID,
        last_used_at: datetime,
    ) -> None:
        statement = (
            update(
                AuthSessionModel
            )
            .where(
                AuthSessionModel.id
                == session_id
            )
            .values(
                current_jti=(
                    current_jti
                ),
                last_used_at=(
                    last_used_at
                ),
            )
        )

        self.session.execute(
            statement
        )

        self.session.flush()

    # =====================================================
    # REVOCATION
    # =====================================================

    def revoke(
        self,
        *,
        session_id: UUID,
        revoked_at: datetime,
        reason: str,
    ) -> None:
        statement = (
            update(
                AuthSessionModel
            )
            .where(
                AuthSessionModel.id
                == session_id
            )
            .where(
                AuthSessionModel.revoked_at
                .is_(None)
            )
            .values(
                revoked_at=(
                    revoked_at
                ),
                revocation_reason=(
                    reason
                ),
            )
        )

        self.session.execute(
            statement
        )

        self.session.flush()

    def revoke_all_for_user(
        self,
        *,
        user_id: UUID,
        revoked_at: datetime,
        reason: str,
    ) -> int:
        statement = (
            update(
                AuthSessionModel
            )
            .where(
                AuthSessionModel.user_id
                == user_id
            )
            .where(
                AuthSessionModel.revoked_at
                .is_(None)
            )
            .values(
                revoked_at=(
                    revoked_at
                ),
                revocation_reason=(
                    reason
                ),
            )
        )

        # Session.execute() is typed by SQLAlchemy as a
        # general Result even though UPDATE operations return
        # a CursorResult at runtime.
        #
        # The explicit cast lets the type checker correctly
        # recognize the rowcount attribute without suppressing
        # type checking.
        result = cast(
            CursorResult[Any],
            self.session.execute(
                statement
            ),
        )

        self.session.flush()

        return (
            result.rowcount
            if result.rowcount >= 0
            else 0
        )

    # =====================================================
    # DOMAIN MAPPING
    # =====================================================

    @staticmethod
    def _to_domain(
        model: AuthSessionModel,
    ) -> AuthSession:
        return AuthSession(
            id=(
                model.id
            ),
            user_id=(
                model.user_id
            ),
            current_jti=(
                model.current_jti
            ),
            created_at=(
                model.created_at
            ),
            last_used_at=(
                model.last_used_at
            ),
            expires_at=(
                model.expires_at
            ),
            revoked_at=(
                model.revoked_at
            ),
            revocation_reason=(
                model.revocation_reason
            ),
        )