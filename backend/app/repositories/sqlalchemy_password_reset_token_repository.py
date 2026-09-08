from __future__ import annotations

import hashlib

from datetime import (
    datetime,
)

from typing import (
    Any,
    cast,
)

from uuid import (
    UUID,
)

from sqlalchemy import (
    text,
)

from sqlalchemy.engine import (
    CursorResult,
)

from sqlalchemy.orm import (
    Session,
)

from app.domain.password_reset_token import (
    PasswordResetToken,
)


class SqlAlchemyPasswordResetTokenRepository:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = (
            session
        )

    # =====================================================
    # CREATE
    # =====================================================

    def create(
        self,
        token: PasswordResetToken,
    ) -> PasswordResetToken:
        """
        Persist a password-reset credential.

        Only the digest of the raw recovery credential is
        stored. The raw bearer token must never enter the
        database.
        """

        statement = text(
            """
            INSERT INTO password_reset_tokens (
                id,
                user_id,
                token_digest,
                credential_fingerprint,
                created_at,
                expires_at,
                used_at,
                invalidated_at
            )
            VALUES (
                :id,
                :user_id,
                :token_digest,
                :credential_fingerprint,
                :created_at,
                :expires_at,
                :used_at,
                :invalidated_at
            )
            """
        )

        self.session.execute(
            statement,
            {
                "id": (
                    token.id
                ),
                "user_id": (
                    token.user_id
                ),
                "token_digest": (
                    token.token_digest
                ),
                "credential_fingerprint": (
                    token
                    .credential_fingerprint
                ),
                "created_at": (
                    token.created_at
                ),
                "expires_at": (
                    token.expires_at
                ),
                "used_at": (
                    token.used_at
                ),
                "invalidated_at": (
                    token.invalidated_at
                ),
            },
        )

        self.session.flush()

        return (
            token
        )

    # =====================================================
    # LOCKED LOOKUP
    # =====================================================

    def get_by_digest_for_update(
        self,
        token_digest: str,
    ) -> PasswordResetToken | None:
        """
        Resolve a reset credential while taking a PostgreSQL
        row lock.

        The row remains locked until the surrounding
        transaction commits or rolls back.

        This serialization protects concurrent attempts to
        consume the same reset credential.
        """

        statement = text(
            """
            SELECT
                id,
                user_id,
                token_digest,
                credential_fingerprint,
                created_at,
                expires_at,
                used_at,
                invalidated_at
            FROM password_reset_tokens
            WHERE token_digest = :token_digest
            FOR UPDATE
            """
        )

        row = (
            self.session.execute(
                statement,
                {
                    "token_digest": (
                        token_digest
                    ),
                },
            )
            .mappings()
            .one_or_none()
        )

        if row is None:
            return (
                None
            )

        return (
            self._to_domain(
                row
            )
        )

    # =====================================================
    # CONSUMPTION
    # =====================================================

    def mark_used(
        self,
        *,
        token_id: UUID,
        used_at: datetime,
    ) -> bool:
        """
        Consume an active reset credential exactly once.

        This compare-and-set update succeeds only if the
        credential is still both:

            unused
            not invalidated

        Concurrent consumers therefore cannot both report
        success.
        """

        statement = text(
            """
            UPDATE password_reset_tokens
            SET used_at = :used_at
            WHERE id = :token_id
              AND used_at IS NULL
              AND invalidated_at IS NULL
            """
        )

        result = cast(
            CursorResult[Any],
            self.session.execute(
                statement,
                {
                    "token_id": (
                        token_id
                    ),
                    "used_at": (
                        used_at
                    ),
                },
            ),
        )

        self.session.flush()

        return (
            int(
                result.rowcount
                or 0
            )
            == 1
        )

    # =====================================================
    # INVALIDATION
    # =====================================================

    def invalidate_active_for_user(
        self,
        *,
        user_id: UUID,
        invalidated_at: datetime,
        exclude_token_id: UUID | None = None,
    ) -> int:
        """
        Invalidate outstanding password-reset credentials for
        one user.

        There are two distinct call paths.

        ISSUANCE
        --------

        request_reset() calls this method with:

            exclude_token_id=None

        Issuance is an invalidate-then-create operation.

        Without serialization, two transactions can both:

            invalidate existing credentials
            see no active credential
            create separate active credentials

        leaving two usable password-reset tokens.

        For the issuance path we therefore acquire a
        PostgreSQL transaction-scoped advisory lock keyed to
        the user before performing invalidation.

        The lock remains held until the transaction commits
        or rolls back.

        CONFIRMATION CLEANUP
        --------------------

        confirm_reset() calls this method with an excluded
        token after it has already locked and consumed the
        winning reset-token row.

        We deliberately DO NOT acquire the issuance advisory
        lock in that path.

        Doing so could create an inverted lock order:

            issuance:
                advisory lock
                then token-row update

            confirmation:
                token-row lock
                then advisory lock

        which could deadlock.

        Confirmation already has its own row-lock and
        compare-and-set protections, so the advisory lock is
        needed only around issuance.
        """

        if (
            exclude_token_id
            is None
        ):
            self._acquire_issuance_lock(
                user_id
            )

        sql = """
            UPDATE password_reset_tokens
            SET invalidated_at = :invalidated_at
            WHERE user_id = :user_id
              AND used_at IS NULL
              AND invalidated_at IS NULL
        """

        parameters: dict[
            str,
            Any,
        ] = {
            "user_id": (
                user_id
            ),
            "invalidated_at": (
                invalidated_at
            ),
        }

        if (
            exclude_token_id
            is not None
        ):
            sql += (
                """
                AND id <> :exclude_token_id
                """
            )

            parameters[
                "exclude_token_id"
            ] = (
                exclude_token_id
            )

        result = cast(
            CursorResult[Any],
            self.session.execute(
                text(
                    sql
                ),
                parameters,
            ),
        )

        self.session.flush()

        return (
            int(
                result.rowcount
                or 0
            )
        )

    # =====================================================
    # ISSUANCE SERIALIZATION
    # =====================================================

    def _acquire_issuance_lock(
        self,
        user_id: UUID,
    ) -> None:
        """
        Serialize password-reset issuance for one account.

        PostgreSQL advisory transaction locks are:

            database coordinated
            invisible to application callers
            automatically released on COMMIT
            automatically released on ROLLBACK

        This is preferable to locking the users table row.

        A user-row lock would introduce a dangerous lock-order
        inversion with password-reset confirmation because
        confirmation first locks the reset-token row and then
        updates the user's password.

        The advisory lock is used only for reset issuance,
        preventing that cycle.
        """

        lock_key = (
            self._issuance_lock_key(
                user_id
            )
        )

        self.session.execute(
            text(
                """
                SELECT pg_advisory_xact_lock(
                    :lock_key
                )
                """
            ),
            {
                "lock_key": (
                    lock_key
                ),
            },
        )

    # =====================================================
    # ADVISORY LOCK KEY
    # =====================================================

    @staticmethod
    def _issuance_lock_key(
        user_id: UUID,
    ) -> int:
        """
        Produce a deterministic signed 64-bit PostgreSQL
        advisory-lock key from a user UUID.

        PostgreSQL's single-key advisory locking API accepts
        a signed BIGINT.

        SHA-256 gives us a stable process-independent mapping
        rather than relying on Python's built-in hash(),
        whose result is intentionally randomized between
        interpreter processes.

        A theoretical 64-bit collision would merely cause
        two unrelated users' issuance operations to serialize
        temporarily. It would not cause them to share reset
        credentials or account state.
        """

        digest = (
            hashlib.sha256(
                user_id.bytes
            )
            .digest()
        )

        unsigned_key = (
            int.from_bytes(
                digest[
                    :8
                ],
                byteorder="big",
                signed=False,
            )
        )

        # PostgreSQL BIGINT is signed:
        #
        #     -2^63 through 2^63 - 1
        #
        # Convert the unsigned 64-bit representation to its
        # equivalent signed value when the high bit is set.

        if (
            unsigned_key
            >= 2**63
        ):
            return (
                unsigned_key
                - 2**64
            )

        return (
            unsigned_key
        )

    # =====================================================
    # DOMAIN MAPPING
    # =====================================================

    @staticmethod
    def _to_domain(
        row,
    ) -> PasswordResetToken:
        return (
            PasswordResetToken(
                id=(
                    row[
                        "id"
                    ]
                ),
                user_id=(
                    row[
                        "user_id"
                    ]
                ),
                token_digest=(
                    row[
                        "token_digest"
                    ]
                ),
                credential_fingerprint=(
                    row[
                        "credential_fingerprint"
                    ]
                ),
                created_at=(
                    row[
                        "created_at"
                    ]
                ),
                expires_at=(
                    row[
                        "expires_at"
                    ]
                ),
                used_at=(
                    row[
                        "used_at"
                    ]
                ),
                invalidated_at=(
                    row[
                        "invalidated_at"
                    ]
                ),
            )
        )