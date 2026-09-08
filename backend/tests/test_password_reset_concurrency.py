from __future__ import annotations

import hashlib

from concurrent.futures import (
    ThreadPoolExecutor,
)

from datetime import (
    datetime,
    timezone,
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

from app.core.security import (
    verify_password,
)

from app.domain.user import (
    UserRole,
)

from app.repositories.sqlalchemy_auth_session_repository import (
    SqlAlchemyAuthSessionRepository,
)

from app.repositories.sqlalchemy_password_reset_token_repository import (
    SqlAlchemyPasswordResetTokenRepository,
)

from app.repositories.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)

from app.services.password_reset_service import (
    InvalidPasswordResetCredentialError,
    PasswordResetService,
)

from app.services.user_service import (
    UserService,
)


# =========================================================
# TEST DATABASE ENGINE
# =========================================================
#
# The normal pytest db_session fixture intentionally owns one
# connection and one transaction.
#
# Real concurrency testing requires independent PostgreSQL
# transactions, so this module opens its own short-lived
# sessions against opsflow_test.
# =========================================================


test_engine = create_engine(
    settings.test_database_url,
    pool_pre_ping=True,
)


# =========================================================
# TEST CREDENTIALS
# =========================================================


OLD_PASSWORD = (
    "VerySecurePassword123!"
)

NEW_PASSWORD_A = (
    "ConcurrentReplacementPasswordA123!"
)

NEW_PASSWORD_B = (
    "ConcurrentReplacementPasswordB456!"
)


# =========================================================
# DATABASE SAFETY
# =========================================================


def require_test_database(
    session: Session,
) -> None:
    """
    Refuse to run the committed concurrency tests against
    anything other than opsflow_test.
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
            "Password-reset concurrency tests must run "
            "against opsflow_test. "
            f"Connected database: {database_name!r}."
        )


# =========================================================
# SERVICE FACTORY
# =========================================================


def build_password_reset_service(
    session: Session,
) -> tuple[
    PasswordResetService,
    SqlAlchemyUserRepository,
    SqlAlchemyPasswordResetTokenRepository,
]:
    """
    Build the real password-reset service with repositories
    bound to the supplied independent transaction.
    """

    user_repository = (
        SqlAlchemyUserRepository(
            session
        )
    )

    reset_repository = (
        SqlAlchemyPasswordResetTokenRepository(
            session
        )
    )

    auth_session_repository = (
        SqlAlchemyAuthSessionRepository(
            session
        )
    )

    service = (
        PasswordResetService(
            user_repository=(
                user_repository
            ),
            password_reset_repository=(
                reset_repository
            ),
            auth_session_repository=(
                auth_session_repository
            ),
        )
    )

    return (
        service,
        user_repository,
        reset_repository,
    )


# =========================================================
# COMMITTED RESET-CREDENTIAL SETUP
# =========================================================


def create_committed_reset_credential(
) -> tuple[
    UUID,
    str,
    UUID,
]:
    """
    Create one user and one password-reset credential, then
    commit them.

    The commit is required because the competing worker
    transactions need to see the same persisted state.

    Returns:

        user id
        raw reset bearer token
        reset-token row id
    """

    with Session(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    ) as session:
        require_test_database(
            session
        )

        (
            service,
            user_repository,
            reset_repository,
        ) = (
            build_password_reset_service(
                session
            )
        )

        user_service = (
            UserService(
                user_repository
            )
        )

        user = (
            user_service.create_user(
                email=(
                    "password-reset-concurrency-"
                    f"{uuid4().hex}"
                    "@example.com"
                ),
                full_name=(
                    "Password Reset "
                    "Concurrency User"
                ),
                password=(
                    OLD_PASSWORD
                ),
                role=(
                    UserRole.OPERATOR
                ),
            )
        )

        issuance = (
            service.request_reset(
                email=(
                    user.email
                ),
            )
        )

        assert (
            issuance
            is not None
        )

        token_digest = (
            hashlib.sha256(
                issuance.raw_token.encode(
                    "utf-8"
                )
            )
            .hexdigest()
        )

        persisted_token = (
            reset_repository
            .get_by_digest_for_update(
                token_digest
            )
        )

        assert (
            persisted_token
            is not None
        )

        user_id = (
            user.id
        )

        raw_token = (
            issuance.raw_token
        )

        reset_token_id = (
            persisted_token.id
        )

        session.commit()

        return (
            user_id,
            raw_token,
            reset_token_id,
        )


# =========================================================
# CLEANUP
# =========================================================


def delete_concurrency_test_user(
    user_id: UUID,
) -> None:
    """
    Remove committed concurrency-test state.

    password_reset_tokens and auth_sessions reference users
    with ON DELETE CASCADE, so deleting the unique test user
    removes dependent recovery/session rows as well.
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
                "Refusing concurrency-test cleanup outside "
                "opsflow_test."
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
# TRANSACTION TIMEOUTS
# =========================================================


def configure_concurrency_timeouts(
    session: Session,
) -> None:
    """
    Protect the test suite from hanging indefinitely if a
    future regression introduces a lock cycle.

    These are PostgreSQL transaction-local settings.
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
# REPOSITORY-LEVEL CONSUMPTION RACE
# =========================================================


def test_concurrent_mark_used_allows_exactly_one_consumer(
) -> None:
    """
    Race two independent transactions directly against the
    repository compare-and-set operation.

    mark_used() contains:

        WHERE used_at IS NULL
          AND invalidated_at IS NULL

    PostgreSQL must therefore allow exactly one transaction
    to change the row from unused to used.
    """

    user_id: UUID | None = None

    try:
        (
            user_id,
            _,
            reset_token_id,
        ) = (
            create_committed_reset_credential()
        )

        start_barrier = (
            Barrier(
                2
            )
        )

        def consume_token(
        ) -> bool:
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

                repository = (
                    SqlAlchemyPasswordResetTokenRepository(
                        session
                    )
                )

                start_barrier.wait(
                    timeout=5
                )

                consumed = (
                    repository.mark_used(
                        token_id=(
                            reset_token_id
                        ),
                        used_at=(
                            datetime.now(
                                timezone.utc
                            )
                        ),
                    )
                )

                session.commit()

                return consumed

        with ThreadPoolExecutor(
            max_workers=2
        ) as executor:
            futures = [
                executor.submit(
                    consume_token
                ),
                executor.submit(
                    consume_token
                ),
            ]

            results = [
                future.result(
                    timeout=20
                )
                for future
                in futures
            ]

        assert (
            results.count(
                True
            )
            == 1
        )

        assert (
            results.count(
                False
            )
            == 1
        )

        # -------------------------------------------------
        # FINAL DATABASE STATE
        # -------------------------------------------------

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
                            used_at,
                            invalidated_at
                        FROM password_reset_tokens
                        WHERE id = :token_id
                        """
                    ),
                    {
                        "token_id": (
                            reset_token_id
                        ),
                    },
                )
                .mappings()
                .one()
            )

            assert (
                row[
                    "used_at"
                ]
                is not None
            )

            assert (
                row[
                    "invalidated_at"
                ]
                is None
            )

    finally:
        if (
            user_id
            is not None
        ):
            delete_concurrency_test_user(
                user_id
            )


# =========================================================
# SERVICE-LEVEL RESET RACE
# =========================================================


def test_concurrent_password_reset_confirmation_allows_one_winner(
) -> None:
    """
    Race the SAME reset bearer token through two independent
    PasswordResetService transactions.

    Both requests begin with:

        same user
        same token
        same original password hash

    but propose two different replacement passwords.

    The required result is:

        one success
        one invalid-credential failure

    It must never be:

        two successes
        two password changes
    """

    user_id: UUID | None = None

    try:
        (
            user_id,
            raw_token,
            reset_token_id,
        ) = (
            create_committed_reset_credential()
        )

        start_barrier = (
            Barrier(
                2
            )
        )

        def confirm_reset(
            new_password: str,
        ) -> tuple[
            str,
            str,
        ]:
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

                (
                    service,
                    _,
                    _,
                ) = (
                    build_password_reset_service(
                        session
                    )
                )

                start_barrier.wait(
                    timeout=5
                )

                try:
                    service.confirm_reset(
                        raw_token=(
                            raw_token
                        ),
                        new_password=(
                            new_password
                        ),
                    )

                    # Row locks and password changes are not
                    # visible to the competing transaction
                    # until this commit occurs.
                    session.commit()

                    return (
                        "success",
                        new_password,
                    )

                except (
                    InvalidPasswordResetCredentialError
                ):
                    session.rollback()

                    return (
                        "invalid",
                        new_password,
                    )

                except Exception:
                    session.rollback()

                    raise

        with ThreadPoolExecutor(
            max_workers=2
        ) as executor:
            futures = [
                executor.submit(
                    confirm_reset,
                    NEW_PASSWORD_A,
                ),
                executor.submit(
                    confirm_reset,
                    NEW_PASSWORD_B,
                ),
            ]

            results = [
                future.result(
                    timeout=25
                )
                for future
                in futures
            ]

        successful_results = [
            result
            for result
            in results
            if result[0]
            == "success"
        ]

        rejected_results = [
            result
            for result
            in results
            if result[0]
            == "invalid"
        ]

        # Exactly one transaction may own this credential.

        assert (
            len(
                successful_results
            )
            == 1
        )

        assert (
            len(
                rejected_results
            )
            == 1
        )

        winning_password = (
            successful_results[
                0
            ][
                1
            ]
        )

        losing_password = (
            rejected_results[
                0
            ][
                1
            ]
        )

        assert (
            winning_password
            != losing_password
        )

        # -------------------------------------------------
        # VERIFY THE PERSISTED PASSWORD
        # -------------------------------------------------

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

            user = (
                user_repository.get_by_id(
                    user_id
                )
            )

            assert (
                user
                is not None
            )

            auth_record = (
                user_repository
                .get_auth_record_by_email(
                    user.email
                )
            )

            assert (
                auth_record
                is not None
            )

            # The final password must be the one belonging
            # to the transaction that actually succeeded.

            assert verify_password(
                winning_password,
                auth_record.hashed_password,
            )

            assert not verify_password(
                losing_password,
                auth_record.hashed_password,
            )

            assert not verify_password(
                OLD_PASSWORD,
                auth_record.hashed_password,
            )

            # -------------------------------------------------
            # VERIFY THE TOKEN WAS CONSUMED ONCE
            # -------------------------------------------------

            token_row = (
                session.execute(
                    text(
                        """
                        SELECT
                            used_at,
                            invalidated_at
                        FROM password_reset_tokens
                        WHERE id = :token_id
                        """
                    ),
                    {
                        "token_id": (
                            reset_token_id
                        ),
                    },
                )
                .mappings()
                .one()
            )

            assert (
                token_row[
                    "used_at"
                ]
                is not None
            )

            assert (
                token_row[
                    "invalidated_at"
                ]
                is None
            )

    finally:
        if (
            user_id
            is not None
        ):
            delete_concurrency_test_user(
                user_id
            )