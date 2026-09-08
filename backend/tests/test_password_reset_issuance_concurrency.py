from __future__ import annotations

import hashlib

from concurrent.futures import (
    ThreadPoolExecutor,
)

from datetime import (
    datetime,
)

from threading import (
    Barrier,
    BrokenBarrierError,
)

from uuid import (
    UUID,
    uuid4,
)

import pytest

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

from app.domain.password_reset_token import (
    PasswordResetToken,
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
# The ordinary pytest db_session fixture intentionally owns
# one connection and one transaction.
#
# Concurrent issuance must instead use two independent
# PostgreSQL transactions so that the test exercises real
# transaction visibility and locking behavior.
# =========================================================


test_engine = create_engine(
    settings.test_database_url,
    pool_pre_ping=True,
)


# =========================================================
# TEST PASSWORDS
# =========================================================


ORIGINAL_PASSWORD = (
    "VerySecurePassword123!"
)

REPLACEMENT_PASSWORD = (
    "ConcurrentReplacementPassword456!"
)


# =========================================================
# DATABASE SAFETY
# =========================================================


def require_test_database(
    session: Session,
) -> None:
    """
    Refuse to execute committed concurrency tests anywhere
    except opsflow_test.

    This suite must commit setup state because independent
    PostgreSQL transactions cannot race against uncommitted
    rows owned by the ordinary rollback fixture.
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

    if database_name != "opsflow_test":
        raise RuntimeError(
            "Password-reset issuance concurrency tests "
            "must run against opsflow_test. "
            f"Connected database: {database_name!r}."
        )


# =========================================================
# TRANSACTION TIMEOUTS
# =========================================================


def configure_concurrency_timeouts(
    session: Session,
) -> None:
    """
    Prevent a locking regression from hanging pytest
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
# SYNCHRONIZING REPOSITORY WRAPPER
# =========================================================


class SynchronizingPasswordResetRepository:
    """
    Thin test-only wrapper around the real SQL repository.

    Its purpose is to make the issuance race deterministic.

    During request_reset(), production currently does:

        invalidate existing credentials
        create replacement credential

    The wrapper places a barrier BETWEEN those operations.

    With two workers this guarantees that both transactions
    finish their invalidation attempt before either worker
    is allowed to create its replacement credential.

    All actual database operations still execute through
    SqlAlchemyPasswordResetTokenRepository.

    BrokenBarrierError is intentionally tolerated. If the
    production implementation later gains real per-account
    serialization, one worker may correctly block before it
    reaches this test barrier. In that case the first worker
    eventually continues rather than deadlocking the test.
    """

    def __init__(
        self,
        *,
        delegate: (
            SqlAlchemyPasswordResetTokenRepository
        ),
        issuance_barrier: Barrier,
    ) -> None:
        self.delegate = (
            delegate
        )

        self.issuance_barrier = (
            issuance_barrier
        )

    def create(
        self,
        token: PasswordResetToken,
    ) -> PasswordResetToken:
        return (
            self.delegate.create(
                token
            )
        )

    def get_by_digest_for_update(
        self,
        token_digest: str,
    ) -> PasswordResetToken | None:
        return (
            self.delegate
            .get_by_digest_for_update(
                token_digest
            )
        )

    def mark_used(
        self,
        *,
        token_id: UUID,
        used_at: datetime,
    ) -> bool:
        return (
            self.delegate.mark_used(
                token_id=(
                    token_id
                ),
                used_at=(
                    used_at
                ),
            )
        )

    def invalidate_active_for_user(
        self,
        *,
        user_id: UUID,
        invalidated_at: datetime,
        exclude_token_id: UUID | None = None,
    ) -> int:
        invalidated_count = (
            self.delegate
            .invalidate_active_for_user(
                user_id=(
                    user_id
                ),
                invalidated_at=(
                    invalidated_at
                ),
                exclude_token_id=(
                    exclude_token_id
                ),
            )
        )

        # request_reset() calls this method without an
        # excluded token.
        #
        # confirm_reset() uses exclude_token_id while doing
        # defensive sibling cleanup, so that path must never
        # participate in the issuance barrier.

        if exclude_token_id is None:
            try:
                self.issuance_barrier.wait(
                    timeout=2
                )

            except BrokenBarrierError:
                # A future production serialization fix may
                # legitimately prevent both workers from
                # reaching this point simultaneously.
                #
                # In that case the database assertions below
                # remain the source of truth.
                pass

        return (
            invalidated_count
        )


# =========================================================
# USER SETUP
# =========================================================


def create_committed_test_user(
) -> tuple[
    UUID,
    str,
]:
    """
    Create one unique account and commit it so both worker
    transactions can resolve the same account.
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

        user = (
            user_service.create_user(
                email=(
                    "reset-issuance-concurrency-"
                    f"{uuid4().hex}"
                    "@example.com"
                ),
                full_name=(
                    "Reset Issuance "
                    "Concurrency User"
                ),
                password=(
                    ORIGINAL_PASSWORD
                ),
                role=(
                    UserRole.OPERATOR
                ),
            )
        )

        user_id = (
            user.id
        )

        user_email = (
            user.email
        )

        session.commit()

        return (
            user_id,
            user_email,
        )


# =========================================================
# CLEANUP
# =========================================================


def delete_test_user(
    user_id: UUID,
) -> None:
    """
    Remove committed state created by this concurrency test.

    Related password-reset and authentication-session rows
    are expected to disappear through their existing
    ON DELETE CASCADE foreign keys.
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

        if database_name != "opsflow_test":
            raise RuntimeError(
                "Refusing concurrency-test cleanup "
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
# PASSWORD-RESET SERVICE FACTORY
# =========================================================


def build_password_reset_service(
    session: Session,
    *,
    issuance_barrier: Barrier | None = None,
) -> PasswordResetService:
    """
    Build the real PasswordResetService.

    When a barrier is supplied, only the reset-token
    repository receives the deterministic race wrapper.
    """

    user_repository = (
        SqlAlchemyUserRepository(
            session
        )
    )

    real_reset_repository = (
        SqlAlchemyPasswordResetTokenRepository(
            session
        )
    )

    auth_session_repository = (
        SqlAlchemyAuthSessionRepository(
            session
        )
    )

    if issuance_barrier is None:
        password_reset_repository = (
            real_reset_repository
        )

    else:
        password_reset_repository = (
            SynchronizingPasswordResetRepository(
                delegate=(
                    real_reset_repository
                ),
                issuance_barrier=(
                    issuance_barrier
                ),
            )
        )

    return (
        PasswordResetService(
            user_repository=(
                user_repository
            ),
            password_reset_repository=(
                password_reset_repository
            ),
            auth_session_repository=(
                auth_session_repository
            ),
        )
    )


# =========================================================
# CONCURRENT ISSUANCE HELPER
# =========================================================


def issue_two_resets_concurrently(
    *,
    user_email: str,
) -> tuple[
    str,
    str,
]:
    """
    Issue two password-reset credentials in independent
    PostgreSQL transactions.

    The test-only repository wrapper forces both workers to
    finish the invalidation phase before either worker can
    create its new credential.
    """

    issuance_barrier = (
        Barrier(
            2
        )
    )

    def issue_reset(
    ) -> str:
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

            service = (
                build_password_reset_service(
                    session,
                    issuance_barrier=(
                        issuance_barrier
                    ),
                )
            )

            try:
                issuance = (
                    service.request_reset(
                        email=(
                            user_email
                        ),
                    )
                )

                assert (
                    issuance
                    is not None
                )

                raw_token = (
                    issuance.raw_token
                )

                session.commit()

                return (
                    raw_token
                )

            except Exception:
                session.rollback()

                raise

    with ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        futures = [
            executor.submit(
                issue_reset
            ),
            executor.submit(
                issue_reset
            ),
        ]

        results = [
            future.result(
                timeout=25
            )
            for future
            in futures
        ]

    assert (
        len(
            results
        )
        == 2
    )

    assert (
        results[0]
        != results[1]
    )

    return (
        results[0],
        results[1],
    )


# =========================================================
# TOKEN DIGEST HELPER
# =========================================================


def digest_reset_token(
    raw_token: str,
) -> str:
    return (
        hashlib.sha256(
            raw_token.encode(
                "utf-8"
            )
        )
        .hexdigest()
    )


# =========================================================
# ACTIVE TOKEN QUERY
# =========================================================


def get_reset_rows(
    *,
    user_id: UUID,
) -> list[
    dict,
]:
    """
    Read all reset-token state for the test account after the
    competing transactions have committed.
    """

    with Session(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    ) as session:
        require_test_database(
            session
        )

        rows = (
            session.execute(
                text(
                    """
                    SELECT
                        id,
                        token_digest,
                        created_at,
                        expires_at,
                        used_at,
                        invalidated_at
                    FROM password_reset_tokens
                    WHERE user_id = :user_id
                    ORDER BY created_at, id
                    """
                ),
                {
                    "user_id": (
                        user_id
                    ),
                },
            )
            .mappings()
            .all()
        )

        return [
            dict(
                row
            )
            for row
            in rows
        ]


# =========================================================
# CONCURRENT ISSUANCE DATABASE INVARIANT
# =========================================================


def test_concurrent_reset_requests_leave_exactly_one_active_credential(
) -> None:
    """
    Two simultaneous password-reset requests for one account
    may both produce unique raw credentials internally.

    After both transactions commit, however, at most ONE
    credential may remain active.

    The other credential must have been superseded.
    """

    user_id: UUID | None = (
        None
    )

    try:
        (
            user_id,
            user_email,
        ) = (
            create_committed_test_user()
        )

        (
            first_raw_token,
            second_raw_token,
        ) = (
            issue_two_resets_concurrently(
                user_email=(
                    user_email
                ),
            )
        )

        assert (
            first_raw_token
            != second_raw_token
        )

        rows = (
            get_reset_rows(
                user_id=(
                    user_id
                )
            )
        )

        # Both requests genuinely issued distinct persisted
        # credentials.

        assert (
            len(
                rows
            )
            == 2
        )

        active_rows = [
            row
            for row
            in rows
            if (
                row[
                    "used_at"
                ]
                is None
                and row[
                    "invalidated_at"
                ]
                is None
            )
        ]

        invalidated_rows = [
            row
            for row
            in rows
            if (
                row[
                    "invalidated_at"
                ]
                is not None
            )
        ]

        # =================================================
        # SECURITY INVARIANT
        # =================================================
        #
        # There must never be two independently usable reset
        # credentials after concurrent issuance.

        assert (
            len(
                active_rows
            )
            == 1
        ), (
            "Concurrent password-reset requests left more "
            "than one active recovery credential."
        )

        assert (
            len(
                invalidated_rows
            )
            == 1
        )

        raw_token_digests = {
            digest_reset_token(
                first_raw_token
            ),
            digest_reset_token(
                second_raw_token
            ),
        }

        persisted_digests = {
            row[
                "token_digest"
            ]
            for row
            in rows
        }

        # Both persisted rows must still contain only token
        # digests—not either raw bearer credential.

        assert (
            persisted_digests
            == raw_token_digests
        )

        assert (
            first_raw_token
            not in persisted_digests
        )

        assert (
            second_raw_token
            not in persisted_digests
        )

    finally:
        if (
            user_id
            is not None
        ):
            delete_test_user(
                user_id
            )


# =========================================================
# CONCURRENT ISSUANCE USABILITY INVARIANT
# =========================================================


def test_only_surviving_concurrent_reset_credential_can_be_consumed(
) -> None:
    """
    After simultaneous issuance:

        one token must survive
        one token must be superseded

    The superseded credential must fail confirmation while
    the surviving credential must still complete recovery.
    """

    user_id: UUID | None = (
        None
    )

    try:
        (
            user_id,
            user_email,
        ) = (
            create_committed_test_user()
        )

        (
            first_raw_token,
            second_raw_token,
        ) = (
            issue_two_resets_concurrently(
                user_email=(
                    user_email
                ),
            )
        )

        rows = (
            get_reset_rows(
                user_id=(
                    user_id
                )
            )
        )

        active_rows = [
            row
            for row
            in rows
            if (
                row[
                    "used_at"
                ]
                is None
                and row[
                    "invalidated_at"
                ]
                is None
            )
        ]

        assert (
            len(
                active_rows
            )
            == 1
        ), (
            "Cannot determine one surviving reset "
            "credential because concurrent issuance left "
            "an invalid active-token state."
        )

        active_digest = (
            active_rows[
                0
            ][
                "token_digest"
            ]
        )

        first_digest = (
            digest_reset_token(
                first_raw_token
            )
        )

        second_digest = (
            digest_reset_token(
                second_raw_token
            )
        )

        if (
            first_digest
            == active_digest
        ):
            surviving_token = (
                first_raw_token
            )

            superseded_token = (
                second_raw_token
            )

        else:
            assert (
                second_digest
                == active_digest
            )

            surviving_token = (
                second_raw_token
            )

            superseded_token = (
                first_raw_token
            )

        # -------------------------------------------------
        # SUPERSEDED TOKEN MUST FAIL
        # -------------------------------------------------

        with Session(
            bind=test_engine,
            autoflush=False,
            expire_on_commit=False,
        ) as session:
            require_test_database(
                session
            )

            service = (
                build_password_reset_service(
                    session
                )
            )

            with pytest.raises(
                InvalidPasswordResetCredentialError
            ):
                service.confirm_reset(
                    raw_token=(
                        superseded_token
                    ),
                    new_password=(
                        REPLACEMENT_PASSWORD
                    ),
                )

            session.rollback()

        # -------------------------------------------------
        # SURVIVING TOKEN MUST SUCCEED
        # -------------------------------------------------

        with Session(
            bind=test_engine,
            autoflush=False,
            expire_on_commit=False,
        ) as session:
            require_test_database(
                session
            )

            service = (
                build_password_reset_service(
                    session
                )
            )

            result = (
                service.confirm_reset(
                    raw_token=(
                        surviving_token
                    ),
                    new_password=(
                        REPLACEMENT_PASSWORD
                    ),
                )
            )

            assert (
                result.user_id
                == user_id
            )

            session.commit()

        # -------------------------------------------------
        # FINAL TOKEN STATE
        # -------------------------------------------------

        final_rows = (
            get_reset_rows(
                user_id=(
                    user_id
                )
            )
        )

        used_rows = [
            row
            for row
            in final_rows
            if (
                row[
                    "used_at"
                ]
                is not None
            )
        ]

        invalidated_rows = [
            row
            for row
            in final_rows
            if (
                row[
                    "invalidated_at"
                ]
                is not None
            )
        ]

        assert (
            len(
                used_rows
            )
            == 1
        )

        assert (
            len(
                invalidated_rows
            )
            == 1
        )

    finally:
        if (
            user_id
            is not None
        ):
            delete_test_user(
                user_id
            )