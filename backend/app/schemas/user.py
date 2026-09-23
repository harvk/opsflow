from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr

from app.core.password_policy import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
)
from app.domain.user import UserRole


class UserCreate(BaseModel):
    email: EmailStr

    full_name: str = Field(
        min_length=1,
        max_length=120,
    )

    password: str = Field(
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
    )


class UserRegistrationRequest(BaseModel):
    """Public self-service account registration payload.

    Registration deliberately accepts only the credentials the user
    controls. Role assignment remains server-side and defaults to the
    least-privilege viewer role.
    """

    email: EmailStr

    password: SecretStr = Field(
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
    )


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime