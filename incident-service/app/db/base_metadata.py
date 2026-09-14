"""
SQLAlchemy metadata registration for Incident Management.

Alembic will import this module so every ORM model owned by the
Incident Service is registered before schema comparison.
"""

from app.db.base import Base
from app.models.incident import IncidentModel  # noqa: F401

__all__ = [
    "Base",
]