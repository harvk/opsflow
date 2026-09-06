from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domain.user import UserRole


class UserCreate(BaseModel):
    email: EmailStr

    full_name: str = Field(
        min_length=1,
        max_length=120,
    )

    password: str = Field(
        min_length=12,
        max_length=128,
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