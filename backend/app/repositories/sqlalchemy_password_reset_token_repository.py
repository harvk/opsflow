from __future__ import annotations

from sqlalchemy.engine.row import (
    RowMapping,
)

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
                "id": token.id,
                "user_id": token.user_id,
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

        return token

    # =====================================================
    # LOCKED LOOKUP
    # =====================================================

    def get_by_digest_for_update(
        self,
        token_digest: str,
    ) -> PasswordResetToken | None:
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
            return None

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
            ] = exclude_token_id

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

        return int(
            result.rowcount
            or 0
        )

    # =========================================================
    # DOMAIN MAPPING
    # =========================================================

    @staticmethod
    def _to_domain(
        row: RowMapping,
    ) -> PasswordResetToken:
        return PasswordResetToken(
            id=row["id"],
            user_id=row["user_id"],
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