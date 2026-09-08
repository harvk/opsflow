from __future__ import annotations

from concurrent.futures import (
    ThreadPoolExecutor,
)

from threading import (
    Barrier,
)

from uuid import (
    UUID,
    uuid4,
)

from sqlalchemy import (
    create_engine,
    text,
)

from sqlalchemy.orm import (
    Session,
)

from app.core.config import (
    settings,
)

from app.domain.user import (
    UserRole,
)

from app.repositories.sqlalchemy_auth_session_repository import (
    SqlAlchemyAuthSessionRepository,
)

from app.repositories.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)

from app.services.authentication_service import (
    AuthenticationService,
    InvalidCredentialsError,
    RefreshTokenReuseError,
)

from app.services.user_service import (
    UserService,
)


# =========================================================
# TEST DATABASE ENGINE
# =========================================================
#
# The ordinary db_session fixture intentionally owns one
# connection and transaction.
#
# Refresh-token concurrency must use independent PostgreSQL
# transactions so SELECT ... FOR UPDATE can be exercised
# for real.
# =========================================================


test_engine = create_engine(
    settings.test_database_url,
    pool_pre_ping=True,
)


# =========================================================
# TEST CREDENTIAL
# =========================================================


TEST_PASSWORD = (
    "VerySecurePassword123!"
)


# =========================================================
# SETUP RESULT
# =========================================================


class RefreshSessionSetup:
    """
    Committed authentication state shared by the competing
    refresh transactions.
    """

    def __init__(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        refresh_token: str,
        csrf_token: str,
    ) -> None:
        self.user_id = (
            user_id
        )

        self.session_id = (
            session_id
        )

        self.refresh_token = (
            refresh_token
        )

        self.csrf_token = (
            csrf_token
        )


# =========================================================
# DATABASE SAFETY
# =========================================================


def require_test_database(
    session: Session,
) -> None:
    """
    Refuse to execute committed concurrency tests anywhere
    other than opsflow_test.
    """

    database_name = (
        session.execute(
            text(
                """
                SELECT current_database()
                """
            )
        )
        .scalar_one()
    )

    if (
        database_name
        != "opsflow_test"
    ):
        raise RuntimeError(
            "Refresh-token concurrency tests must run "
            "against opsflow_test. "
            f"Connected database: {database_name!r}."
        )


# =========================================================
# LOCK TIMEOUTS
# =========================================================


def configure_concurrency_timeouts(
    session: Session,
) -> None:
    """
    Prevent a future locking regression from hanging pytest
    indefinitely.
    """

    session.execute(
        text(
            """
            SET LOCAL lock_timeout = '10s'
            """
        )
    )

    session.execute(
        text(
            """
            SET LOCAL statement_timeout = '15s'
            """
        )
    )


# =========================================================
# SERVICE FACTORY
# =========================================================


def build_authentication_service(
    session: Session,
) -> AuthenticationService:
    """
    Build the real authentication service against one
    independent SQLAlchemy transaction.
    """

    user_repository = (
        SqlAlchemyUserRepository(
            session
        )
    )

    auth_session_repository = (
        SqlAlchemyAuthSessionRepository(
            session
        )
    )

    return (
        AuthenticationService(
            repository=(
                user_repository
            ),
            auth_session_repository=(
                auth_session_repository
            ),
        )
    )


# =========================================================
# COMMITTED AUTHENTICATION SESSION
# =========================================================


def create_committed_authentication_session(
) -> RefreshSessionSetup:
    """
    Create:

        one active user
        one persistent authentication session
        one refresh token
        one session-bound CSRF token

    and COMMIT them so independent worker transactions can
    race against the same auth_sessions row.
    """

    with Session(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    ) as session:
        require_test_database(
            session
        )

        user_repository = (
            SqlAlchemyUserRepository(
                session
            )
        )

        user_service = (
            UserService(
                user_repository
            )
        )

        authentication_service = (
            build_authentication_service(
                session
            )
        )

        user = (
            user_service.create_user(
                email=(
                    "refresh-concurrency-"
                    f"{uuid4().hex}"
                    "@example.com"
                ),
                full_name=(
                    "Refresh Concurrency User"
                ),
                password=(
                    TEST_PASSWORD
                ),
                role=(
                    UserRole.OPERATOR
                ),
            )
        )

        authentication_result = (
            authentication_service
            .issue_authentication_result(
                user
            )
        )

        setup = (
            RefreshSessionSetup(
                user_id=(
                    user.id
                ),
                session_id=(
                    authentication_result
                    .session_id
                ),
                refresh_token=(
                    authentication_result
                    .refresh_token
                ),
                csrf_token=(
                    authentication_result
                    .csrf_token
                ),
            )
        )

        session.commit()

        return (
            setup
        )


# =========================================================
# CLEANUP
# =========================================================


def delete_test_user(
    user_id: UUID,
) -> None:
    """
    Delete committed state created by this suite.

    Existing auth-session foreign-key cascade behavior removes
    the persistent sessions belonging to the test user.
    """

    with test_engine.begin() as connection:
        database_name = (
            connection.execute(
                text(
                    """
                    SELECT current_database()
                    """
                )
            )
            .scalar_one()
        )

        if (
            database_name
            != "opsflow_test"
        ):
            raise RuntimeError(
                "Refusing refresh-concurrency cleanup "
                "outside opsflow_test."
            )

        connection.execute(
            text(
                """
                DELETE FROM users
                WHERE id = :user_id
                """
            ),
            {
                "user_id": (
                    user_id
                ),
            },
        )


# =========================================================
# PERSISTED SESSION READER
# =========================================================


def read_auth_session(
    *,
    session_id: UUID,
) -> dict:
    """
    Read final persistent-session state after competing
    transactions have completed.
    """

    with Session(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    ) as session:
        require_test_database(
            session
        )

        row = (
            session.execute(
                text(
                    """
                    SELECT
                        id,
                        user_id,
                        current_jti,
                        created_at,
                        last_used_at,
                        expires_at,
                        revoked_at,
                        revocation_reason
                    FROM auth_sessions
                    WHERE id = :session_id
                    """
                ),
                {
                    "session_id": (
                        session_id
                    ),
                },
            )
            .mappings()
            .one()
        )

        return (
            dict(
                row
            )
        )


# =========================================================
# CONCURRENT REFRESH RESULT
# =========================================================


class ConcurrentRefreshResult:
    """
    Result returned by one competing worker.
    """

    def __init__(
        self,
        *,
        outcome: str,
        replacement_token: str | None = None,
        replacement_token_id: UUID | None = None,
        session_id: UUID | None = None,
    ) -> None:
        self.outcome = (
            outcome
        )

        self.replacement_token = (
            replacement_token
        )

        self.replacement_token_id = (
            replacement_token_id
        )

        self.session_id = (
            session_id
        )


# =========================================================
# CONCURRENT ROTATION HELPER
# =========================================================


def race_same_refresh_token(
    setup: RefreshSessionSetup,
) -> list[
    ConcurrentRefreshResult
]:
    """
    Submit the same refresh credential through two separate
    Password/AuthenticationService transactions.

    Both workers start together.

    Only one may successfully rotate the session.

    The other must observe the changed jti and trigger
    refresh-token-family revocation.
    """

    start_barrier = (
        Barrier(
            2
        )
    )

    def rotate(
    ) -> ConcurrentRefreshResult:
        with Session(
            bind=test_engine,
            autoflush=False,
            expire_on_commit=False,
        ) as session:
            require_test_database(
                session
            )

            configure_concurrency_timeouts(
                session
            )

            authentication_service = (
                build_authentication_service(
                    session
                )
            )

            start_barrier.wait(
                timeout=5
            )

            try:
                result = (
                    authentication_service
                    .rotate_refresh_token_with_csrf(
                        setup.refresh_token,
                        csrf_cookie=(
                            setup.csrf_token
                        ),
                        csrf_header=(
                            setup.csrf_token
                        ),
                    )
                )

                session.commit()

                return (
                    ConcurrentRefreshResult(
                        outcome=(
                            "success"
                        ),
                        replacement_token=(
                            result
                            .refresh_token
                        ),
                        replacement_token_id=(
                            result
                            .refresh_token_id
                        ),
                        session_id=(
                            result
                            .session_id
                        ),
                    )
                )

            except (
                RefreshTokenReuseError
            ) as exc:
                # IMPORTANT:
                #
                # Reuse detection intentionally performs a
                # server-side revocation BEFORE raising.
                #
                # The production HTTP route catches this
                # exception and returns a response, allowing
                # the request transaction to commit.
                #
                # Therefore this direct-service concurrency
                # test must also commit the revocation.

                session.commit()

                return (
                    ConcurrentRefreshResult(
                        outcome=(
                            "reuse"
                        ),
                        session_id=(
                            exc.session_id
                        ),
                    )
                )

            except Exception:
                session.rollback()

                raise

    with ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        futures = [
            executor.submit(
                rotate
            ),
            executor.submit(
                rotate
            ),
        ]

        return [
            future.result(
                timeout=25
            )
            for future
            in futures
        ]


# =========================================================
# CONCURRENT ROTATION INVARIANT
# =========================================================


def test_concurrent_refresh_rotation_allows_one_rotation_and_detects_reuse(
) -> None:
    """
    Two simultaneous uses of the same refresh credential must
    not both create valid descendants.

    Required result:

        one successful rotation
        one reuse detection
        complete session-family revocation
    """

    setup: (
        RefreshSessionSetup
        | None
    ) = None

    try:
        setup = (
            create_committed_authentication_session()
        )

        results = (
            race_same_refresh_token(
                setup
            )
        )

        successful_results = [
            result
            for result
            in results
            if (
                result.outcome
                == "success"
            )
        ]

        reuse_results = [
            result
            for result
            in results
            if (
                result.outcome
                == "reuse"
            )
        ]

        # -------------------------------------------------
        # EXACTLY ONE WINNER
        # -------------------------------------------------

        assert (
            len(
                successful_results
            )
            == 1
        )

        # -------------------------------------------------
        # EXACTLY ONE REPLAY DETECTION
        # -------------------------------------------------

        assert (
            len(
                reuse_results
            )
            == 1
        )

        winner = (
            successful_results[
                0
            ]
        )

        reuse = (
            reuse_results[
                0
            ]
        )

        assert (
            winner.session_id
            == setup.session_id
        )

        assert (
            reuse.session_id
            == setup.session_id
        )

        assert (
            winner
            .replacement_token
            is not None
        )

        assert (
            winner
            .replacement_token_id
            is not None
        )

        # -------------------------------------------------
        # FINAL SERVER-SIDE SESSION STATE
        # -------------------------------------------------

        row = (
            read_auth_session(
                session_id=(
                    setup.session_id
                )
            )
        )

        # The winner really did rotate current_jti before the
        # replaying transaction obtained its lock.

        assert (
            row[
                "current_jti"
            ]
            == (
                winner
                .replacement_token_id
            )
        )

        # The subsequent replay must revoke the complete
        # persistent session/token family.

        assert (
            row[
                "revoked_at"
            ]
            is not None
        )

        assert (
            row[
                "revocation_reason"
            ]
            == "refresh_token_reuse"
        )

    finally:
        if (
            setup
            is not None
        ):
            delete_test_user(
                setup.user_id
            )


# =========================================================
# WINNER'S TOKEN MUST ALSO DIE
# =========================================================


def test_replay_revocation_invalidates_the_winning_replacement_token(
) -> None:
    """
    A subtle but critical token-family property:

    Worker A can successfully rotate the old token and obtain
    replacement token B.

    If worker B then presents the already-consumed old token,
    that is evidence that the token family may be compromised.

    The server revokes the SESSION, not merely the replayed
    token.

    Therefore replacement token B must also become unusable.
    """

    setup: (
        RefreshSessionSetup
        | None
    ) = None

    try:
        setup = (
            create_committed_authentication_session()
        )

        results = (
            race_same_refresh_token(
                setup
            )
        )

        successful_results = [
            result
            for result
            in results
            if (
                result.outcome
                == "success"
            )
        ]

        reuse_results = [
            result
            for result
            in results
            if (
                result.outcome
                == "reuse"
            )
        ]

        assert (
            len(
                successful_results
            )
            == 1
        )

        assert (
            len(
                reuse_results
            )
            == 1
        )

        winner = (
            successful_results[
                0
            ]
        )

        replacement_token = (
            winner
            .replacement_token
        )

        assert (
            replacement_token
            is not None
        )

        # -------------------------------------------------
        # TRY THE WINNER'S REPLACEMENT AFTER FAMILY REVOKE
        # -------------------------------------------------

        with Session(
            bind=test_engine,
            autoflush=False,
            expire_on_commit=False,
        ) as session:
            require_test_database(
                session
            )

            authentication_service = (
                build_authentication_service(
                    session
                )
            )

            try:
                authentication_service.rotate_refresh_token_with_csrf(
                    replacement_token,
                    csrf_cookie=(
                        setup.csrf_token
                    ),
                    csrf_header=(
                        setup.csrf_token
                    ),
                )

            except (
                InvalidCredentialsError
            ):
                session.rollback()

            else:
                session.rollback()

                raise AssertionError(
                    "A replacement refresh token remained "
                    "usable after refresh-token reuse "
                    "revoked its persistent session."
                )

        # -------------------------------------------------
        # SERVER STATE REMAINS REVOKED
        # -------------------------------------------------

        row = (
            read_auth_session(
                session_id=(
                    setup.session_id
                )
            )
        )

        assert (
            row[
                "revoked_at"
            ]
            is not None
        )

        assert (
            row[
                "revocation_reason"
            ]
            == "refresh_token_reuse"
        )

    finally:
        if (
            setup
            is not None
        ):
            delete_test_user(
                setup.user_id
            )