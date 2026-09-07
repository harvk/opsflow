from __future__ import annotations

from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import hmac

from uuid import (
    UUID,
    uuid4,
)

from app.core.config import (
    settings,
)

from app.core.security import (
    DUMMY_PASSWORD_HASH,
    ReauthenticationClaims,
    RefreshTokenClaims,
    TokenValidationError,
    create_access_token,
    create_csrf_token,
    create_reauthentication_token,
    create_refresh_token,
    decode_access_token,
    decode_reauthentication_token,
    decode_refresh_token,
    hash_password,
    reauthentication_credential_matches,
    validate_csrf_token,
    verify_password,
)

from app.domain.auth_session import (
    AuthSession,
)

from app.domain.user import (
    User,
)

from app.repositories.auth_session_repository import (
    AuthSessionRepository,
)

from app.repositories.user_repository import (
    UserRepository,
)


# =========================================================
# RESULT TYPES
# =========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class AuthenticationResult:
    """
    Result of establishing a brand-new browser
    authentication session.
    """

    access_token: str
    refresh_token: str
    csrf_token: str

    user: User

    session_id: UUID
    refresh_token_id: UUID


@dataclass(
    frozen=True,
    slots=True,
)
class ResolvedRefreshSession:
    """
    Validated persistent refresh-session context.
    """

    user: User
    session: AuthSession
    claims: RefreshTokenClaims


@dataclass(
    frozen=True,
    slots=True,
)
class RefreshRotationResult:
    """
    Result of atomically replacing one refresh credential
    with another.
    """

    access_token: str
    refresh_token: str

    user: User

    session_id: UUID

    previous_refresh_token_id: UUID
    refresh_token_id: UUID


@dataclass(
    frozen=True,
    slots=True,
)
class SessionRevocationResult:
    """
    Result of revoking one persistent authentication
    session.
    """

    user: User
    session_id: UUID


@dataclass(
    frozen=True,
    slots=True,
)
class ReauthenticationResult:
    """
    Result of successfully verifying the current password
    for sensitive-action step-up authentication.
    """

    reauth_token: str
    expires_in_seconds: int


@dataclass(
    frozen=True,
    slots=True,
)
class PasswordChangeResult:
    """
    Result of a successful password change.
    """

    user_id: UUID
    revoked_sessions: int


# =========================================================
# AUTHENTICATION ERRORS
# =========================================================


class AuthenticationError(
    Exception
):
    """
    Base exception for authentication-domain failures.

    API routes translate subclasses into appropriate HTTP
    responses.
    """

    pass


class InvalidCredentialsError(
    AuthenticationError
):
    """
    An ordinary authentication credential could not be
    trusted.
    """

    pass


class InactiveUserError(
    AuthenticationError
):
    """
    Authentication resolved to an inactive account.
    """

    pass


class ReauthenticationError(
    AuthenticationError
):
    """
    Recent sensitive-action authentication proof could not
    be trusted.

    Examples include:

        invalid reauthentication JWT
        expired reauthentication JWT
        wrong current password
        stale credential fingerprint
        proof belonging to another user
    """

    pass


class PasswordChangeError(
    AuthenticationError
):
    """
    The replacement password violates a password-change
    invariant.
    """

    pass


class RefreshTokenReuseError(
    AuthenticationError
):
    """
    A previously consumed refresh credential was presented
    again.

    The associated persistent authentication session is
    revoked before this exception is raised.
    """

    def __init__(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
    ) -> None:
        super().__init__(
            "Refresh-token reuse detected."
        )

        self.user_id = (
            user_id
        )

        self.session_id = (
            session_id
        )


class InvalidCsrfTokenError(
    Exception
):
    """
    CSRF validation failure.

    This remains separate from AuthenticationError because
    the API translates it to HTTP 403 rather than ordinary
    credential failure.
    """

    pass


# =========================================================
# AUTHENTICATION SERVICE
# =========================================================


class AuthenticationService:
    def __init__(
        self,
        repository: UserRepository,
        auth_session_repository: (
            AuthSessionRepository
        ),
    ) -> None:
        self.repository = (
            repository
        )

        self.auth_session_repository = (
            auth_session_repository
        )

    # =====================================================
    # USERNAME / PASSWORD AUTHENTICATION
    # =====================================================

    def authenticate(
        self,
        *,
        email: str,
        password: str,
    ) -> User:
        """
        Authenticate ordinary username/password credentials.
        """

        normalized_email = (
            email
            .strip()
            .lower()
        )

        auth_record = (
            self.repository
            .get_auth_record_by_email(
                normalized_email
            )
        )

        if (
            auth_record
            is None
        ):
            # Preserve approximately equivalent password
            # hashing work for nonexistent accounts.
            verify_password(
                password,
                DUMMY_PASSWORD_HASH,
            )

            raise InvalidCredentialsError(
                "Invalid credentials."
            )

        password_is_valid = (
            verify_password(
                password,
                auth_record.hashed_password,
            )
        )

        if not password_is_valid:
            raise InvalidCredentialsError(
                "Invalid credentials."
            )

        if not (
            auth_record
            .user
            .is_active
        ):
            raise InactiveUserError(
                "The user account is inactive."
            )

        return (
            auth_record.user
        )

    # =====================================================
    # SENSITIVE-ACTION REAUTHENTICATION
    # =====================================================

    def reauthenticate(
        self,
        user: User,
        *,
        password: str,
    ) -> ReauthenticationResult:
        """
        Verify an already-authenticated user's current
        password and issue short-lived step-up proof.
        """

        self._require_active_user(
            user
        )

        auth_record = (
            self.repository
            .get_auth_record_by_email(
                user.email
                .strip()
                .lower()
            )
        )

        if (
            auth_record
            is None
        ):
            verify_password(
                password,
                DUMMY_PASSWORD_HASH,
            )

            raise ReauthenticationError(
                "Reauthentication failed."
            )

        password_is_valid = (
            verify_password(
                password,
                auth_record.hashed_password,
            )
        )

        if (
            not password_is_valid
            or auth_record.user.id
            != user.id
        ):
            raise ReauthenticationError(
                "Reauthentication failed."
            )

        token = (
            create_reauthentication_token(
                user.id,
                credential_hash=(
                    auth_record
                    .hashed_password
                ),
            )
        )

        return ReauthenticationResult(
            reauth_token=(
                token
            ),
            expires_in_seconds=(
                settings
                .reauth_token_expire_minutes
                * 60
            ),
        )

    def resolve_reauthentication_token(
        self,
        token: str,
    ) -> User:
        """
        Validate the reauthentication JWT and confirm that
        its credential fingerprint still matches the user's
        currently stored password hash.
        """

        claims = (
            self._decode_reauthentication_token(
                token
            )
        )

        user = (
            self._resolve_active_user(
                claims.user_id
            )
        )

        auth_record = (
            self.repository
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
            raise ReauthenticationError(
                "Reauthentication proof "
                "is invalid."
            )

        if not (
            reauthentication_credential_matches(
                hashed_password=(
                    auth_record
                    .hashed_password
                ),
                credential_fingerprint=(
                    claims
                    .credential_fingerprint
                ),
            )
        ):
            raise ReauthenticationError(
                "Reauthentication proof "
                "is stale."
            )

        return user

    # =====================================================
    # PASSWORD CHANGE
    # =====================================================

    def change_password(
        self,
        user: User,
        *,
        reauth_token: str,
        new_password: str,
    ) -> PasswordChangeResult:
        """
        Change the currently authenticated user's password.

        Required invariants:

            bearer identity already established

            valid recent reauthentication proof

            proof belongs to this user

            credential fingerprint is still current

            new password satisfies policy

            new password differs from current password

            database password update uses compare-and-set

            all persistent refresh sessions are revoked
        """

        self._require_active_user(
            user
        )

        # -------------------------------------------------
        # REAUTHENTICATION PROOF
        # -------------------------------------------------

        claims = (
            self._decode_reauthentication_token(
                reauth_token
            )
        )

        if (
            claims.user_id
            != user.id
        ):
            raise ReauthenticationError(
                "Reauthentication proof does "
                "not belong to this user."
            )

        # -------------------------------------------------
        # CURRENT CREDENTIAL RECORD
        # -------------------------------------------------

        auth_record = (
            self.repository
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
            raise ReauthenticationError(
                "Reauthentication proof "
                "cannot be validated."
            )

        current_hashed_password = (
            auth_record
            .hashed_password
        )

        # -------------------------------------------------
        # PROOF MUST MATCH CURRENT CREDENTIAL
        # -------------------------------------------------

        if not (
            reauthentication_credential_matches(
                hashed_password=(
                    current_hashed_password
                ),
                credential_fingerprint=(
                    claims
                    .credential_fingerprint
                ),
            )
        ):
            raise ReauthenticationError(
                "Reauthentication proof "
                "is stale."
            )

        # -------------------------------------------------
        # PASSWORD POLICY
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
            raise PasswordChangeError(
                "The new password must differ "
                "from the current password."
            )

        replacement_hash = (
            hash_password(
                new_password
            )
        )

        # -------------------------------------------------
        # COMPARE-AND-SET PASSWORD UPDATE
        # -------------------------------------------------

        password_updated = (
            self.repository
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
            raise ReauthenticationError(
                "The credential changed while "
                "the operation was in progress."
            )

        # -------------------------------------------------
        # REVOKE ALL PERSISTENT SESSIONS
        # -------------------------------------------------

        now = datetime.now(
            timezone.utc
        )

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
                    "password_changed"
                ),
            )
        )

        return PasswordChangeResult(
            user_id=(
                user.id
            ),
            revoked_sessions=(
                revoked_sessions
            ),
        )

    # =====================================================
    # INITIAL LOGIN SESSION
    # =====================================================

    def issue_authentication_result(
        self,
        user: User,
    ) -> AuthenticationResult:
        """
        Establish a new persistent login session.
        """

        self._require_active_user(
            user
        )

        now = datetime.now(
            timezone.utc
        )

        expires_at = (
            now
            + timedelta(
                days=(
                    settings
                    .refresh_token_expire_days
                )
            )
        )

        session_id = (
            uuid4()
        )

        refresh_token_id = (
            uuid4()
        )

        auth_session = AuthSession(
            id=(
                session_id
            ),
            user_id=(
                user.id
            ),
            current_jti=(
                refresh_token_id
            ),
            created_at=(
                now
            ),
            last_used_at=(
                now
            ),
            expires_at=(
                expires_at
            ),
            revoked_at=None,
            revocation_reason=None,
        )

        persisted_session = (
            self.auth_session_repository
            .create(
                auth_session
            )
        )

        access_token = (
            create_access_token(
                user.id
            )
        )

        refresh_token = (
            create_refresh_token(
                user.id,
                session_id=(
                    persisted_session.id
                ),
                token_id=(
                    persisted_session
                    .current_jti
                ),
                expires_at=(
                    persisted_session
                    .expires_at
                ),
            )
        )

        csrf_token = (
            create_csrf_token(
                persisted_session.id
            )
        )

        return AuthenticationResult(
            access_token=(
                access_token
            ),
            refresh_token=(
                refresh_token
            ),
            csrf_token=(
                csrf_token
            ),
            user=(
                user
            ),
            session_id=(
                persisted_session.id
            ),
            refresh_token_id=(
                persisted_session
                .current_jti
            ),
        )

    # =====================================================
    # ACCESS TOKEN
    # =====================================================

    def issue_access_token(
        self,
        user: User,
    ) -> str:
        """
        Issue another short-lived access JWT.
        """

        self._require_active_user(
            user
        )

        return create_access_token(
            user.id
        )

    def resolve_access_token(
        self,
        token: str,
    ) -> User:
        """
        Resolve an access JWT into the current active user.
        """

        try:
            user_id = (
                decode_access_token(
                    token
                )
            )

        except TokenValidationError as exc:
            raise InvalidCredentialsError(
                "Invalid access token."
            ) from exc

        return (
            self._resolve_active_user(
                user_id
            )
        )

    # =====================================================
    # NON-ROTATING REFRESH RESOLUTION
    # =====================================================

    def resolve_refresh_token_with_csrf(
        self,
        token: str,
        *,
        csrf_cookie: str | None,
        csrf_header: str | None,
    ) -> ResolvedRefreshSession:
        """
        Validate a refresh credential without consuming it.
        """

        claims = (
            self._decode_refresh_token_with_csrf(
                token,
                csrf_cookie=(
                    csrf_cookie
                ),
                csrf_header=(
                    csrf_header
                ),
            )
        )

        session = (
            self.auth_session_repository
            .get_by_id(
                claims.session_id
            )
        )

        if (
            session
            is None
        ):
            raise InvalidCredentialsError(
                "The authentication session "
                "does not exist."
            )

        now = datetime.now(
            timezone.utc
        )

        self._require_usable_session(
            session=(
                session
            ),
            claims=(
                claims
            ),
            now=(
                now
            ),
        )

        if (
            session.current_jti
            != claims.token_id
        ):
            raise InvalidCredentialsError(
                "The refresh token is no "
                "longer current."
            )

        user = (
            self._resolve_active_user(
                claims.user_id
            )
        )

        return ResolvedRefreshSession(
            user=(
                user
            ),
            session=(
                session
            ),
            claims=(
                claims
            ),
        )

    # =====================================================
    # ATOMIC REFRESH ROTATION
    # =====================================================

    def rotate_refresh_token_with_csrf(
        self,
        token: str,
        *,
        csrf_cookie: str | None,
        csrf_header: str | None,
    ) -> RefreshRotationResult:
        """
        Consume the current refresh credential and issue its
        one-time replacement.
        """

        claims = (
            self._decode_refresh_token_with_csrf(
                token,
                csrf_cookie=(
                    csrf_cookie
                ),
                csrf_header=(
                    csrf_header
                ),
            )
        )

        session = (
            self.auth_session_repository
            .get_by_id_for_update(
                claims.session_id
            )
        )

        if (
            session
            is None
        ):
            raise InvalidCredentialsError(
                "The authentication session "
                "does not exist."
            )

        now = datetime.now(
            timezone.utc
        )

        self._require_usable_session(
            session=(
                session
            ),
            claims=(
                claims
            ),
            now=(
                now
            ),
        )

        # -------------------------------------------------
        # REFRESH-TOKEN REUSE
        # -------------------------------------------------

        if (
            session.current_jti
            != claims.token_id
        ):
            self.auth_session_repository.revoke(
                session_id=(
                    session.id
                ),
                revoked_at=(
                    now
                ),
                reason=(
                    "refresh_token_reuse"
                ),
            )

            raise RefreshTokenReuseError(
                user_id=(
                    session.user_id
                ),
                session_id=(
                    session.id
                ),
            )

        user = (
            self._resolve_active_user(
                claims.user_id
            )
        )

        replacement_token_id = (
            uuid4()
        )

        self.auth_session_repository.update_current_token(
            session_id=(
                session.id
            ),
            current_jti=(
                replacement_token_id
            ),
            last_used_at=(
                now
            ),
        )

        replacement_refresh_token = (
            create_refresh_token(
                user.id,
                session_id=(
                    session.id
                ),
                token_id=(
                    replacement_token_id
                ),
                expires_at=(
                    session.expires_at
                ),
            )
        )

        access_token = (
            create_access_token(
                user.id
            )
        )

        return RefreshRotationResult(
            access_token=(
                access_token
            ),
            refresh_token=(
                replacement_refresh_token
            ),
            user=(
                user
            ),
            session_id=(
                session.id
            ),
            previous_refresh_token_id=(
                claims.token_id
            ),
            refresh_token_id=(
                replacement_token_id
            ),
        )

    # =====================================================
    # CURRENT SESSION REVOCATION
    # =====================================================

    def revoke_refresh_session_with_csrf(
        self,
        token: str,
        *,
        csrf_cookie: str | None,
        csrf_header: str | None,
    ) -> SessionRevocationResult:
        """
        Validate and revoke the current persistent browser
        authentication session.
        """

        claims = (
            self._decode_refresh_token_with_csrf(
                token,
                csrf_cookie=(
                    csrf_cookie
                ),
                csrf_header=(
                    csrf_header
                ),
            )
        )

        session = (
            self.auth_session_repository
            .get_by_id_for_update(
                claims.session_id
            )
        )

        if (
            session
            is None
        ):
            raise InvalidCredentialsError(
                "The authentication session "
                "does not exist."
            )

        now = datetime.now(
            timezone.utc
        )

        self._require_usable_session(
            session=(
                session
            ),
            claims=(
                claims
            ),
            now=(
                now
            ),
        )

        if (
            session.current_jti
            != claims.token_id
        ):
            self.auth_session_repository.revoke(
                session_id=(
                    session.id
                ),
                revoked_at=(
                    now
                ),
                reason=(
                    "refresh_token_reuse"
                ),
            )

            raise RefreshTokenReuseError(
                user_id=(
                    session.user_id
                ),
                session_id=(
                    session.id
                ),
            )

        user = (
            self._resolve_active_user(
                claims.user_id
            )
        )

        self.auth_session_repository.revoke(
            session_id=(
                session.id
            ),
            revoked_at=(
                now
            ),
            reason=(
                "logout"
            ),
        )

        return SessionRevocationResult(
            user=(
                user
            ),
            session_id=(
                session.id
            ),
        )

    # =====================================================
    # REVOKE ALL USER SESSIONS
    # =====================================================

    def revoke_all_sessions_for_user(
        self,
        user: User,
    ) -> int:
        """
        Revoke all refresh sessions belonging to one user.
        """

        self._require_active_user(
            user
        )

        now = datetime.now(
            timezone.utc
        )

        return (
            self.auth_session_repository
            .revoke_all_for_user(
                user_id=(
                    user.id
                ),
                revoked_at=(
                    now
                ),
                reason=(
                    "logout_all"
                ),
            )
        )

    # =====================================================
    # TOKEN VALIDATION HELPERS
    # =====================================================

    def _decode_reauthentication_token(
        self,
        token: str,
    ) -> ReauthenticationClaims:
        """
        Translate low-level JWT validation failures into a
        service-layer reauthentication failure.
        """

        try:
            return (
                decode_reauthentication_token(
                    token
                )
            )

        except TokenValidationError as exc:
            raise ReauthenticationError(
                "Reauthentication proof "
                "is invalid."
            ) from exc

    def _decode_refresh_token_with_csrf(
        self,
        token: str,
        *,
        csrf_cookie: str | None,
        csrf_header: str | None,
    ) -> RefreshTokenClaims:
        """
        Decode a refresh JWT and validate its session-bound
        CSRF proof.
        """

        try:
            claims = (
                decode_refresh_token(
                    token
                )
            )

        except TokenValidationError as exc:
            raise InvalidCredentialsError(
                "Invalid refresh token."
            ) from exc

        self._validate_csrf(
            session_id=(
                claims.session_id
            ),
            csrf_cookie=(
                csrf_cookie
            ),
            csrf_header=(
                csrf_header
            ),
        )

        return claims

    # =====================================================
    # SESSION INVARIANTS
    # =====================================================

    @staticmethod
    def _require_usable_session(
        *,
        session: AuthSession,
        claims: RefreshTokenClaims,
        now: datetime,
    ) -> None:
        """
        Validate persistent authentication-session state
        other than current_jti.
        """

        if (
            session.revoked_at
            is not None
        ):
            raise InvalidCredentialsError(
                "The authentication session "
                "has been revoked."
            )

        if (
            session.expires_at
            <= now
        ):
            raise InvalidCredentialsError(
                "The authentication session "
                "has expired."
            )

        if (
            session.user_id
            != claims.user_id
        ):
            raise InvalidCredentialsError(
                "The refresh token does not "
                "belong to this session."
            )

    # =====================================================
    # CSRF VALIDATION
    # =====================================================

    @staticmethod
    def _validate_csrf(
        *,
        session_id: UUID,
        csrf_cookie: str | None,
        csrf_header: str | None,
    ) -> None:
        """
        Require a valid signed double-submit CSRF proof.
        """

        if (
            csrf_cookie is None
            or csrf_header is None
        ):
            raise InvalidCsrfTokenError(
                "CSRF proof is missing."
            )

        if not hmac.compare_digest(
            csrf_cookie.encode(
                "utf-8"
            ),
            csrf_header.encode(
                "utf-8"
            ),
        ):
            raise InvalidCsrfTokenError(
                "CSRF proof does not match."
            )

        if not validate_csrf_token(
            session_id,
            csrf_cookie,
        ):
            raise InvalidCsrfTokenError(
                "CSRF token signature "
                "is invalid."
            )

    # =====================================================
    # PASSWORD POLICY
    # =====================================================

    @staticmethod
    def _validate_new_password(
        password: str,
    ) -> None:
        """
        OpsFlow currently uses passwords as a single
        authentication factor.

        Minimum:
            15 Unicode code points

        Maximum:
            128 Unicode code points

        No arbitrary composition requirements are imposed.
        """

        if (
            len(
                password
            )
            < 15
        ):
            raise PasswordChangeError(
                "The new password must contain "
                "at least 15 characters."
            )

        if (
            len(
                password
            )
            > 128
        ):
            raise PasswordChangeError(
                "The new password must not exceed "
                "128 characters."
            )

    # =====================================================
    # USER RESOLUTION
    # =====================================================

    def _resolve_active_user(
        self,
        user_id: UUID,
    ) -> User:
        """
        Resolve a UUID into an active user.
        """

        user = (
            self.repository
            .get_by_id(
                user_id
            )
        )

        if (
            user
            is None
        ):
            raise InvalidCredentialsError(
                "The authenticated user "
                "no longer exists."
            )

        self._require_active_user(
            user
        )

        return user

    @staticmethod
    def _require_active_user(
        user: User,
    ) -> None:
        """
        Require the user account to remain active.
        """

        if not user.is_active:
            raise InactiveUserError(
                "The user account is inactive."
            )