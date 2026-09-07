from __future__ import annotations

from collections.abc import (
    Generator,
)

from sqlalchemy import (
    create_engine,
)

from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from app.core.config import (
    settings,
)


# =========================================================
# DATABASE ENGINE
# =========================================================

engine = create_engine(
    settings.database_url,

    # Verify pooled connections before handing them to the
    # application.
    #
    # This helps recover from stale/disconnected PostgreSQL
    # connections without requiring an application restart.
    pool_pre_ping=True,
)


# =========================================================
# SESSION FACTORY
# =========================================================

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,

    # Repository/service operations explicitly control when
    # SQLAlchemy sends pending work to PostgreSQL.
    #
    # This is useful for authentication-session operations
    # where flush timing and row-lock behavior matter.
    autoflush=False,

    # Keep loaded ORM state available after commit.
    #
    # Request-scoped services should not unexpectedly trigger
    # another database query merely because the transaction
    # committed.
    expire_on_commit=False,
)


# =========================================================
# REQUEST-SCOPED DATABASE SESSION
# =========================================================

def get_db_session(
) -> Generator[
    Session,
    None,
    None,
]:
    """
    Provide one SQLAlchemy Session / transaction boundary for
    a FastAPI request.

    Transaction ownership belongs here rather than inside
    repositories or services.

    Successful request flow:

        create Session
            ↓
        yield Session
            ↓
        route/service/repository work
            ↓
        repository flushes as needed
            ↓
        route completes normally
            ↓
        COMMIT

    Failure flow:

        create Session
            ↓
        yield Session
            ↓
        unhandled exception escapes route
            ↓
        ROLLBACK
            ↓
        re-raise exception

    The session is closed in all cases.

    This boundary is particularly important for persistent
    authentication sessions:

        login
            -> auth_sessions INSERT is committed

        refresh
            -> current_jti rotation is committed

        logout
            -> revoked_at is committed

        logout-all
            -> all revocations are committed

        refresh-token reuse
            -> the endpoint catches the security exception
               and returns a Response normally, allowing the
               revocation transaction to commit

    Repositories should therefore flush but should not call
    commit() themselves.
    """

    session = (
        SessionLocal()
    )

    try:
        # FastAPI executes the endpoint while this generator
        # is suspended.
        yield session

        # Endpoint completed normally.
        #
        # Persist the complete request unit of work.
        session.commit()

    except Exception:
        # An exception escaped the endpoint/dependency chain.
        #
        # Discard the entire request transaction so partial
        # business/security state is not persisted.
        session.rollback()

        raise

    finally:
        # Always return the connection to SQLAlchemy's pool.
        session.close()