from __future__ import annotations

from concurrent.futures import (
    ThreadPoolExecutor,
)

from threading import (
    Barrier,
)

from uuid import (
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

from app.repositories.sqlalchemy_auth_session_repository import (
    SqlAlchemyAuthSessionRepository,
)

from app.repositories.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)

from app.services.authentication_service import (
    AuthenticationService,
    RefreshTokenReuseError,
)

from app.services.user_service import (
    UserService,
)


TEST_PASSWORD = (
    "VerySecurePassword123!"
)


def build_authentication_service(
    session: Session,
) -> AuthenticationService:
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

    return AuthenticationService(
        repository=(
            user_repository
        ),
        auth_session_repository=(
            auth_session_repository
        ),
    )


def test_parallel_refresh_allows_one_rotation_and_detects_reuse(
) -> None:
    """
    Verify the actual PostgreSQL SELECT ... FOR UPDATE
    behavior using two independent database connections.

    Exactly one transaction should consume J1.

    The second transaction should wake after the first
    transaction commits, observe that current_jti changed,
    classify its J1 as reuse, and revoke the session.
    """

    engine = create_engine(
        settings.test_database_url,
        pool_pre_ping=True,
    )

    user_id = None

    try:
        # =================================================
        # COMMITTED SETUP
        # =================================================

        with Session(
            engine,
            expire_on_commit=False,
        ) as setup_session:
            user_repository = (
                SqlAlchemyUserRepository(
                    setup_session
                )
            )

            user_service = (
                UserService(
                    user_repository
                )
            )

            user = user_service.create_user(
                email=(
                    f"concurrent-refresh-"
                    f"{uuid4().hex}"
                    "@example.com"
                ),
                full_name=(
                    "Concurrent Refresh Test User"
                ),
                password=(
                    TEST_PASSWORD
                ),
            )

            authentication_service = (
                build_authentication_service(
                    setup_session
                )
            )

            login_result = (
                authentication_service
                .issue_authentication_result(
                    user
                )
            )

            user_id = user.id

            session_id = (
                login_result.session_id
            )

            original_refresh_token = (
                login_result.refresh_token
            )

            csrf_token = (
                login_result.csrf_token
            )

            # A real commit is required so independent
            # connections can see and lock this row.
            setup_session.commit()

        # =================================================
        # SYNCHRONIZED WORKERS
        # =================================================

        barrier = Barrier(
            2
        )

        def rotate_once() -> str:
            with Session(
                engine,
                expire_on_commit=False,
            ) as worker_session:
                authentication_service = (
                    build_authentication_service(
                        worker_session
                    )
                )

                barrier.wait()

                try:
                    (
                        authentication_service
                        .rotate_refresh_token_with_csrf(
                            original_refresh_token,
                            csrf_cookie=(
                                csrf_token
                            ),
                            csrf_header=(
                                csrf_token
                            ),
                        )
                    )

                except RefreshTokenReuseError:
                    # The service has written the revocation.
                    #
                    # RefreshTokenReuseError is an application
                    # security exception rather than a
                    # database exception, so the transaction
                    # remains committable.
                    worker_session.commit()

                    return "reuse"

                else:
                    worker_session.commit()

                    return "success"

        with ThreadPoolExecutor(
            max_workers=2
        ) as executor:
            futures = [
                executor.submit(
                    rotate_once
                )
                for _ in range(
                    2
                )
            ]

            outcomes = [
                future.result(
                    timeout=10
                )
                for future in futures
            ]

        # One transaction consumes the credential.
        #
        # The second sees the replacement jti after acquiring
        # the row lock and classifies its copy as replay.
        assert sorted(
            outcomes
        ) == [
            "reuse",
            "success",
        ]

        # =================================================
        # FINAL DATABASE STATE
        # =================================================

        with Session(
            engine,
            expire_on_commit=False,
        ) as verification_session:
            repository = (
                SqlAlchemyAuthSessionRepository(
                    verification_session
                )
            )

            persisted_session = (
                repository.get_by_id(
                    session_id
                )
            )

            assert (
                persisted_session
                is not None
            )

            assert (
                persisted_session.revoked_at
                is not None
            )

            assert (
                persisted_session
                .revocation_reason
                == "refresh_token_reuse"
            )

    finally:
        # This test intentionally performs real commits, so
        # unlike ordinary tests it cannot rely on the outer
        # rollback fixture for cleanup.
        if user_id is not None:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        DELETE FROM users
                        WHERE id = CAST(
                            :user_id AS uuid
                        )
                        """
                    ),
                    {
                        "user_id": (
                            str(
                                user_id
                            )
                        )
                    },
                )

        engine.dispose()