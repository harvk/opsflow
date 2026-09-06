"""
SQLAlchemy metadata registration.

Alembic imports this module so every ORM model is loaded
before Base.metadata is inspected for schema changes.
"""

from app.db.base import Base

# Import ORM models for their metadata-registration side effect.
#
# These imports may appear "unused", but importing each model
# causes SQLAlchemy to register its table with Base.metadata.

from app.models.user import UserModel  # noqa: F401
from app.models.service import ServiceModel  # noqa: F401
from app.models.incident import IncidentModel  # noqa: F401
from app.models.auth_session import AuthSessionModel  # noqa: F401


__all__ = [
    "Base",
]