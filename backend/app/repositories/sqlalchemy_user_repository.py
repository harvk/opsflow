from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.user import User, UserAuthRecord, UserRole
from app.models.user import UserModel
from app.repositories.user_repository import UserRepository


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _to_domain(model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            full_name=model.full_name,
            role=model.role,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def add(
        self,
        *,
        email: str,
        full_name: str,
        hashed_password: str,
        role: UserRole = UserRole.VIEWER,
        is_active: bool = True,
    ) -> User:
        model = UserModel(
            email=email,
            full_name=full_name,
            hashed_password=hashed_password,
            role=role,
            is_active=is_active,
        )

        self.session.add(model)
        self.session.flush()
        self.session.refresh(model)

        return self._to_domain(model)

    def get_by_id(
        self,
        user_id: UUID,
    ) -> User | None:
        model = self.session.get(
            UserModel,
            user_id,
        )

        if model is None:
            return None

        return self._to_domain(model)

    def get_by_email(
        self,
        email: str,
    ) -> User | None:
        statement = select(UserModel).where(
            UserModel.email == email
        )

        model = self.session.scalar(statement)

        if model is None:
            return None

        return self._to_domain(model)

    def get_auth_record_by_email(
        self,
        email: str,
    ) -> UserAuthRecord | None:
        statement = select(UserModel).where(
            UserModel.email == email
        )

        model = self.session.scalar(statement)

        if model is None:
            return None

        return UserAuthRecord(
            user=self._to_domain(model),
            hashed_password=model.hashed_password,
        )