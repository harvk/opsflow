from __future__ import annotations

from dataclasses import dataclass

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from uuid import (
    UUID,
    uuid4,
)

from app.core.password_reset_tokens import (
    create_password_reset_credential_fingerprint,
    digest_password_reset_token,
    generate_password_reset_token,
    password_reset_credential_matches,
)

from app.core.security import (
    hash_password,
    verify_password,
)

from app.domain.password_reset_token import (
    PasswordResetToken,
)

from app.repositories.auth_session_repository import (
    AuthSessionRepository,
)

from app.repositories.password_reset_token_repository import (
    PasswordResetTokenRepository,
)

from app.repositories.user_repository import (
    UserRepository,
)


# =========================================================
# CONFIGURATION
# =========================================================

DEFAULT_PASSWORD_RESET_TTL = (
    timedelta(
        minutes=30
    )
)


# =========================================================
# RESULT TYPES
# =========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class PasswordResetIssuance:
    """
    Internal result used by the future delivery layer.

    The raw token must never be returned by the public
    password-reset request endpoint.
    """

    email: str

    token: str

    expires_at: datetime


@dataclass(
    frozen=True,
    slots=True,
)
class PasswordResetCompletion:
    """
    Result of a completed recovery operation.
    """

    user_id: UUID

    revoked_sessions: int


# =========================================================
# PASSWORD RESET ERRORS
# =========================================================


class PasswordResetError(
    Exception
):
    """
    Base password-recovery domain failure.
    """

    pass


class InvalidPasswordResetTokenError(
    PasswordResetError
):
    """
    Reset proof cannot be trusted.

    The API layer should deliberately avoid exposing which
    exact validation condition failed.
    """

    pass


class PasswordResetPasswordError(
    PasswordResetError
):
    """
    The requested replacement password violates password
    policy.
    """

    pass


# =========================================================
# SERVICE
# =========================================================


class PasswordResetService:
    def __init__(
        self,
        *,
        user_repository: UserRepository,
        reset_token_repository: (
            PasswordResetTokenRepository
        ),
        auth_session_repository: (
            AuthSessionRepository
        ),
        token_ttl: timedelta = (
            DEFAULT_PASSWORD_RESET_TTL
        ),
    ) -> None:
        if (
            token_ttl
            <= timedelta(
                seconds=0
            )
        ):
            raise ValueError(
                "Password-reset TTL must be positive."
            )

        self.user_repository = (
            user_repository
        )

        self.reset_token_repository = (
            reset_token_repository
        )

        self.auth_session_repository = (
            auth_session_repository
        )

        self.token_ttl = (
            token_ttl
        )

    # =====================================================
    # RESET REQUEST
    # =====================================================

    def request_password_reset(
        self,
        *,
        email: str,
    ) -> PasswordResetIssuance | None:
        """
        Create an internal password-reset credential.

        Returning None for unknown/inactive accounts is an
        INTERNAL distinction only.

        Phase 6.4D-3B will ensure that the public HTTP
        response is identical regardless of whether this
        method returns an issuance.
        """

        normalized_email = (
            email
            .strip()
            .lower()
        )

        auth_record = (
            self.user_repository
            .get_auth_record_by_email(
                normalized_email
            )
        )

        if (
            auth_record
            is None
        ):
            return None

        if not (
            auth_record
            .user
            .is_active
        ):
            return None

        now = datetime.now(
            timezone.utc
        )

        expires_at = (
            now
            + self.token_ttl
        )

        raw_token = (
            generate_password_reset_token()
        )

        token_digest = (
            digest_password_reset_token(
                raw_token
            )
        )

        credential_fingerprint = (
            create_password_reset_credential_fingerprint(
                auth_record
                .hashed_password
            )
        )

        # Supersede previous outstanding recovery links.
        self.reset_token_repository.invalidate_active_for_user(
            user_id=(
                auth_record
                .user
                .id
            ),
            invalidated_at=(
                now
            ),
        )

        reset_token = (
            PasswordResetToken(
                id=(
                    uuid4()
                ),
                user_id=(
                    auth_record
                    .user
                    .id
                ),
                token_digest=(
                    token_digest
                ),
                credential_fingerprint=(
                    credential_fingerprint
                ),
                created_at=(
                    now
                ),
                expires_at=(
                    expires_at
                ),
                used_at=None,
                invalidated_at=None,
            )
        )

        self.reset_token_repository.create(
            reset_token
        )

        return PasswordResetIssuance(
            email=(
                auth_record
                .user
                .email
            ),
            token=(
                raw_token
            ),
            expires_at=(
                expires_at
            ),
        )

    # =====================================================
    # RESET COMPLETION
    # =====================================================

    def reset_password(
        self,
        *,
        token: str,
        new_password: str,
    ) -> PasswordResetCompletion:
        """
        Consume one reset token and replace the associated
        account password.

        Security sequence:

            1. hash submitted opaque token
            2. SELECT reset row FOR UPDATE
            3. validate token lifecycle
            4. resolve current user
            5. verify credential-version binding
            6. validate replacement password
            7. reject current-password reuse
            8. compare-and-set current password hash
            9. mark reset token single-use consumed
           10. invalidate other recovery tokens
           11. revoke every persistent auth session

        No new authentication session is created here.
        """

        token_digest = (
            self._digest_submitted_token(
                token
            )
        )

        reset_token = (
            self.reset_token_repository
            .get_by_digest_for_update(
                token_digest
            )
        )

        now = datetime.now(
            timezone.utc
        )

        # -------------------------------------------------
        # TOKEN LIFECYCLE
        # -------------------------------------------------

        if (
            reset_token
            is None
        ):
            raise (
                self._invalid_token_error()
            )

        if not (
            reset_token.is_usable(
                now=now
            )
        ):
            raise (
                self._invalid_token_error()
            )

        # -------------------------------------------------
        # USER
        # -------------------------------------------------

        user = (
            self.user_repository
            .get_by_id(
                reset_token.user_id
            )
        )

        if (
            user is None
            or not user.is_active
        ):
            raise (
                self._invalid_token_error()
            )

        # -------------------------------------------------
        # CURRENT CREDENTIAL RECORD
        # -------------------------------------------------

        auth_record = (
            self.user_repository
            .get_auth_record_by_email(
                user.email
                .strip()
                .lower()
            )
        )

        if (
            auth_record is None
            or auth_record.user.id
            != reset_token.user_id
        ):
            raise (
                self._invalid_token_error()
            )

        current_hashed_password = (
            auth_record
            .hashed_password
        )

        # -------------------------------------------------
        # CREDENTIAL VERSION
        # -------------------------------------------------

        # If a password change or another successful reset
        # occurred after this token was issued, this reset
        # credential immediately becomes stale.
        if not (
            password_reset_credential_matches(
                hashed_password=(
                    current_hashed_password
                ),
                credential_fingerprint=(
                    reset_token
                    .credential_fingerprint
                ),
            )
        ):
            raise (
                self._invalid_token_error()
            )

        # -------------------------------------------------
        # PASSWORD POLICY
        # -------------------------------------------------

        self._validate_new_password(
            new_password
        )

        # -------------------------------------------------
        # PASSWORD REUSE
        # -------------------------------------------------

        if verify_password(
            new_password,
            current_hashed_password,
        ):
            raise PasswordResetPasswordError(
                "The new password must differ "
                "from the current password."
            )

        replacement_hash = (
            hash_password(
                new_password
            )
        )

        # -------------------------------------------------
        # ATOMIC CREDENTIAL UPDATE
        # -------------------------------------------------

        password_updated = (
            self.user_repository
            .update_password_hash_if_current(
                user_id=(
                    user.id
                ),
                expected_hashed_password=(
                    current_hashed_password
                ),
                new_hashed_password=(
                    replacement_hash
                ),
            )
        )

        if not password_updated:
            # Another credential update occurred between our
            # read and write.
            #
            # The request transaction must roll back rather
            # than overwriting that newer credential.
            raise (
                self._invalid_token_error()
            )

        # -------------------------------------------------
        # SINGLE-USE CONSUMPTION
        # -------------------------------------------------

        consumed = (
            self.reset_token_repository
            .mark_used(
                token_id=(
                    reset_token.id
                ),
                used_at=(
                    now
                ),
            )
        )

        if not consumed:
            # Under the row lock this should not normally be
            # reachable. Treat it as a failed security
            # invariant and let the request transaction roll
            # back the password update.
            raise (
                self._invalid_token_error()
            )

        # -------------------------------------------------
        # INVALIDATE OTHER RESET TOKENS
        # -------------------------------------------------

        self.reset_token_repository.invalidate_active_for_user(
            user_id=(
                user.id
            ),
            invalidated_at=(
                now
            ),
            exclude_token_id=(
                reset_token.id
            ),
        )

        # -------------------------------------------------
        # REVOKE AUTHENTICATION SESSIONS
        # -------------------------------------------------

        revoked_sessions = (
            self.auth_session_repository
            .revoke_all_for_user(
                user_id=(
                    user.id
                ),
                revoked_at=(
                    now
                ),
                reason=(
                    "password_reset"
                ),
            )
        )

        return PasswordResetCompletion(
            user_id=(
                user.id
            ),
            revoked_sessions=(
                revoked_sessions
            ),
        )

    # =====================================================
    # INTERNAL HELPERS
    # =====================================================

    @staticmethod
    def _digest_submitted_token(
        token: str,
    ) -> str:
        try:
            return (
                digest_password_reset_token(
                    token
                )
            )

        except ValueError as exc:
            raise (
                PasswordResetService
                ._invalid_token_error()
            ) from exc

    @staticmethod
    def _invalid_token_error(
    ) -> InvalidPasswordResetTokenError:
        """
        Keep all token-lifecycle failures deliberately
        indistinguishable.
        """

        return InvalidPasswordResetTokenError(
            "The password-reset token is "
            "invalid or expired."
        )

    @staticmethod
    def _validate_new_password(
        password: str,
    ) -> None:
        """
        Keep reset-password policy consistent with the
        authenticated password-change flow:

            minimum 15 Unicode code points
            maximum 128 Unicode code points
        """

        if (
            len(
                password
            )
            < 15
        ):
            raise PasswordResetPasswordError(
                "The new password must contain "
                "at least 15 characters."
            )

        if (
            len(
                password
            )
            > 128
        ):
            raise PasswordResetPasswordError(
                "The new password must not exceed "
                "128 characters."
            )