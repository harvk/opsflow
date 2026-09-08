from __future__ import annotations

from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import hashlib
import hmac
import secrets

from uuid import (
    UUID,
    uuid4,
)

from app.core.password_policy import (
    PasswordPolicyViolation,
    validate_new_password,
)

from app.core.security import (
    create_reauthentication_fingerprint,
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
# RESULTS
# =========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class PasswordResetIssueResult:
    """
    Internal result of issuing a recovery credential.

    raw_token must never be:

        stored in the database
        logged
        returned by the public API

    The delivery layer is the only production consumer of
    this value.
    """

    user_id: UUID

    email: str

    raw_token: str

    expires_at: datetime


@dataclass(
    frozen=True,
    slots=True,
)
class PasswordResetCompletionResult:
    user_id: UUID

    revoked_sessions: int


# =========================================================
# ERRORS
# =========================================================


class PasswordResetError(
    Exception
):
    pass


class InvalidPasswordResetCredentialError(
    PasswordResetError
):
    """
    Reset credential cannot be trusted.

    Public HTTP responses intentionally collapse the exact
    reason into one generic error.
    """

    pass


class PasswordResetPasswordError(
    PasswordResetError
):
    """
    Replacement password violates a password invariant.
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
        password_reset_repository: (
            PasswordResetTokenRepository
        ),
        auth_session_repository: (
            AuthSessionRepository
        ),
        token_ttl: timedelta = timedelta(
            minutes=30
        ),
    ) -> None:
        self.user_repository = (
            user_repository
        )

        self.password_reset_repository = (
            password_reset_repository
        )

        self.auth_session_repository = (
            auth_session_repository
        )

        self.token_ttl = (
            token_ttl
        )

    # =====================================================
    # REQUEST RESET
    # =====================================================

    def request_reset(
        self,
        *,
        email: str,
    ) -> PasswordResetIssueResult | None:
        """
        Create a one-time recovery credential for an eligible
        account.

        Unknown and inactive accounts return None rather than
        raising. The HTTP layer deliberately turns both None
        and a real result into the exact same 202 response.
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
            auth_record is None
            or not auth_record.user.is_active
        ):
            return None

        now = datetime.now(
            timezone.utc
        )

        # A newly requested credential supersedes all
        # previous outstanding reset credentials.
        (
            self.password_reset_repository
            .invalidate_active_for_user(
                user_id=(
                    auth_record
                    .user
                    .id
                ),
                invalidated_at=now,
            )
        )

        raw_token = (
            secrets.token_urlsafe(
                48
            )
        )

        token_digest = (
            self._digest_token(
                raw_token
            )
        )

        credential_fingerprint = (
            create_reauthentication_fingerprint(
                auth_record
                .hashed_password
            )
        )

        expires_at = (
            now
            + self.token_ttl
        )

        reset_token = (
            PasswordResetToken(
                id=uuid4(),
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
                created_at=now,
                expires_at=(
                    expires_at
                ),
                used_at=None,
                invalidated_at=None,
            )
        )

        (
            self.password_reset_repository
            .create(
                reset_token
            )
        )

        return PasswordResetIssueResult(
            user_id=(
                auth_record
                .user
                .id
            ),
            email=(
                auth_record
                .user
                .email
            ),
            raw_token=(
                raw_token
            ),
            expires_at=(
                expires_at
            ),
        )

    # =====================================================
    # CONFIRM RESET
    # =====================================================

    def confirm_reset(
        self,
        *,
        raw_token: str,
        new_password: str,
    ) -> PasswordResetCompletionResult:
        """
        Atomically consume a one-time recovery credential.

        Successful recovery:

            changes the password
            consumes the reset credential
            invalidates sibling reset credentials
            revokes every persistent auth session
        """

        token_digest = (
            self._digest_token(
                raw_token
            )
        )

        reset_token = (
            self.password_reset_repository
            .get_by_digest_for_update(
                token_digest
            )
        )

        if reset_token is None:
            raise (
                InvalidPasswordResetCredentialError(
                    "Password reset credential "
                    "is invalid."
                )
            )

        now = datetime.now(
            timezone.utc
        )

        self._require_usable_token(
            reset_token,
            now=now,
        )

        user = (
            self.user_repository
            .get_by_id(
                reset_token
                .user_id
            )
        )

        if (
            user is None
            or not user.is_active
        ):
            raise (
                InvalidPasswordResetCredentialError(
                    "Password reset credential "
                    "is invalid."
                )
            )

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
            != user.id
        ):
            raise (
                InvalidPasswordResetCredentialError(
                    "Password reset credential "
                    "is invalid."
                )
            )

        current_hashed_password = (
            auth_record
            .hashed_password
        )

        expected_fingerprint = (
            create_reauthentication_fingerprint(
                current_hashed_password
            )
        )

        if not hmac.compare_digest(
            expected_fingerprint.encode(
                "utf-8"
            ),
            reset_token
            .credential_fingerprint
            .encode(
                "utf-8"
            ),
        ):
            raise (
                InvalidPasswordResetCredentialError(
                    "Password reset credential "
                    "is stale."
                )
            )

        # -------------------------------------------------
        # SHARED SERVER-SIDE PASSWORD POLICY
        # -------------------------------------------------

        self._validate_new_password(
            new_password
        )

        # -------------------------------------------------
        # CANNOT REUSE CURRENT PASSWORD
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
        # ATOMIC PASSWORD UPDATE
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
            raise (
                InvalidPasswordResetCredentialError(
                    "The credential changed while "
                    "the reset was in progress."
                )
            )

        # -------------------------------------------------
        # CONSUME RESET CREDENTIAL
        # -------------------------------------------------

        token_consumed = (
            self.password_reset_repository
            .mark_used(
                token_id=(
                    reset_token
                    .id
                ),
                used_at=now,
            )
        )

        if not token_consumed:
            raise (
                InvalidPasswordResetCredentialError(
                    "Password reset credential "
                    "could not be consumed."
                )
            )

        # -------------------------------------------------
        # INVALIDATE SIBLING RESET CREDENTIALS
        # -------------------------------------------------

        (
            self.password_reset_repository
            .invalidate_active_for_user(
                user_id=(
                    user.id
                ),
                invalidated_at=now,
                exclude_token_id=(
                    reset_token
                    .id
                ),
            )
        )

        # -------------------------------------------------
        # REVOKE EVERY PERSISTENT SESSION
        # -------------------------------------------------

        revoked_sessions = (
            self.auth_session_repository
            .revoke_all_for_user(
                user_id=(
                    user.id
                ),
                revoked_at=now,
                reason=(
                    "password_reset"
                ),
            )
        )

        return (
            PasswordResetCompletionResult(
                user_id=(
                    user.id
                ),
                revoked_sessions=(
                    revoked_sessions
                ),
            )
        )

    # =====================================================
    # SECURITY HELPERS
    # =====================================================

    @staticmethod
    def _digest_token(
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

    @staticmethod
    def _require_usable_token(
        token: PasswordResetToken,
        *,
        now: datetime,
    ) -> None:
        if (
            token.used_at
            is not None
        ):
            raise (
                InvalidPasswordResetCredentialError(
                    "Password reset credential "
                    "has already been used."
                )
            )

        if (
            token.invalidated_at
            is not None
        ):
            raise (
                InvalidPasswordResetCredentialError(
                    "Password reset credential "
                    "has been invalidated."
                )
            )

        if (
            token.expires_at
            <= now
        ):
            raise (
                InvalidPasswordResetCredentialError(
                    "Password reset credential "
                    "has expired."
                )
            )

    # =====================================================
    # PASSWORD POLICY TRANSLATION
    # =====================================================

    @staticmethod
    def _validate_new_password(
        password: str,
    ) -> None:
        """
        Apply the canonical core password policy while
        preserving PasswordResetService's established domain
        exception contract.
        """

        try:
            validate_new_password(
                password
            )

        except PasswordPolicyViolation as exc:
            raise PasswordResetPasswordError(
                str(
                    exc
                )
            ) from exc