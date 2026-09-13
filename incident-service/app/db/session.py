from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)


SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)


def get_db_session() -> Generator[Session, None, None]:
    """
    Provide one transaction-controlled SQLAlchemy Session.

    Repositories flush pending changes but do not commit them.
    The request/session boundary commits after successful work
    and rolls back when an exception escapes.
    """

    session = SessionLocal()

    try:
        yield session

        session.commit()

    except Exception:
        session.rollback()

        raise

    finally:
        session.close()