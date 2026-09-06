from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth_session import (
    AuthSessionModel,
)

from app.domain.auth_session import (
    AuthSession,
)

from app.repositories.auth_session_repository import (
    AuthSessionRepository,
)


class SqlAlchemyAuthSessionRepository(
    AuthSessionRepository
):
    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    def create(
        self,
        session: AuthSession,
    ) -> AuthSession:
        model = AuthSessionModel(
            id=session.id,
            user_id=session.user_id,
            current_refresh_jti=(
                session.current_refresh_jti
            ),
            created_at=session.created_at,
            expires_at=session.expires_at,
            last_refreshed_at=(
                session.last_refreshed_at
            ),
            revoked_at=session.revoked_at,
            revocation_reason=(
                session.revocation_reason
            ),
        )

        self.db.add(
            model
        )

        self.db.flush()

        return session

    def get_by_id(
        self,
        session_id: UUID,
        *,
        for_update: bool = False,
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

        if for_update:
            statement = (
                statement.with_for_update()
            )

        model = (
            self.db.execute(
                statement
            )
            .scalar_one_or_none()
        )

        if model is None:
            return None

        return self._to_domain(
            model
        )

    def update(
        self,
        session: AuthSession,
    ) -> AuthSession:
        model = self.db.get(
            AuthSessionModel,
            session.id,
        )

        if model is None:
            raise LookupError(
                "Authentication session "
                "does not exist."
            )

        model.current_refresh_jti = (
            session.current_refresh_jti
        )

        model.last_refreshed_at = (
            session.last_refreshed_at
        )

        model.revoked_at = (
            session.revoked_at
        )

        model.revocation_reason = (
            session.revocation_reason
        )

        self.db.flush()

        return session

    @staticmethod
    def _to_domain(
        model: AuthSessionModel,
    ) -> AuthSession:
        return AuthSession(
            id=model.id,
            user_id=model.user_id,
            current_refresh_jti=(
                model.current_refresh_jti
            ),
            created_at=model.created_at,
            expires_at=model.expires_at,
            last_refreshed_at=(
                model.last_refreshed_at
            ),
            revoked_at=model.revoked_at,
            revocation_reason=(
                model.revocation_reason
            ),
        )