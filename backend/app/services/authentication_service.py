from __future__ import annotations

from dataclasses import dataclass
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
    RefreshTokenClaims,
    TokenValidationError,
    create_access_token,
    create_csrf_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
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
# AUTHENTICATION RESULT TYPES
# =========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class AuthenticationResult:
    """
    Complete browser authentication state created by an
    initial username/password login.
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
    Result of validating an existing refresh credential
    without consuming it.
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
    Result of atomically consuming one refresh token and
    replacing it with another.
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
    Result of successfully revoking one persistent browser
    authentication session.
    """

    user: User
    session_id: UUID


# =========================================================
# AUTHENTICATION ERRORS
# =========================================================


class AuthenticationError(
    Exception
):
    """
    Base class for authentication-layer failures.
    """

    pass


class InvalidCredentialsError(
    AuthenticationError
):
    """
    Credentials could not be trusted.
    """

    pass


class InactiveUserError(
    AuthenticationError
):
    """
    Authentication state resolved to an inactive account.
    """

    pass


class RefreshTokenReuseError(
    AuthenticationError
):
    """
    A validly signed refresh JWT belongs to an existing
    authentication session but its jti is no longer the
    session's current_jti.

    The persistent session is revoked before this exception
    is raised.
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

        self.user_id = user_id
        self.session_id = session_id


class InvalidCsrfTokenError(
    Exception
):
    """
    CSRF failures remain distinct from ordinary
    authentication failures.
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
        self.repository = repository

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
        normalized_email = (
            email
            .strip()
            .lower()
        )

        auth_record = (
            self
            .repository
            .get_auth_record_by_email(
                normalized_email
            )
        )

        if auth_record is None:
            # Perform equivalent hashing work even when the
            # submitted account does not exist.
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

        if not auth_record.user.is_active:
            raise InactiveUserError(
                "The user account is inactive."
            )

        return auth_record.user

    # =====================================================
    # INITIAL LOGIN SESSION
    # =====================================================

    def issue_authentication_result(
        self,
        user: User,
    ) -> AuthenticationResult:
        """
        Establish a brand-new persistent authentication
        session.

        This method belongs to LOGIN only.
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

        session_id = uuid4()

        refresh_token_id = uuid4()

        auth_session = AuthSession(
            id=session_id,
            user_id=user.id,
            current_jti=(
                refresh_token_id
            ),
            created_at=now,
            last_used_at=now,
            expires_at=expires_at,
            revoked_at=None,
            revocation_reason=None,
        )

        persisted_session = (
            self
            .auth_session_repository
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
            user=user,
            session_id=(
                persisted_session.id
            ),
            refresh_token_id=(
                persisted_session
                .current_jti
            ),
        )

    # =====================================================
    # ACCESS-TOKEN ISSUANCE
    # =====================================================

    def issue_access_token(
        self,
        user: User,
    ) -> str:
        self._require_active_user(
            user
        )

        return create_access_token(
            user.id
        )

    # =====================================================
    # ACCESS-TOKEN RESOLUTION
    # =====================================================

    def resolve_access_token(
        self,
        token: str,
    ) -> User:
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

        return self._resolve_active_user(
            user_id
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
        Validate refresh JWT + CSRF + persistent-session
        state without consuming the refresh credential.
        """

        claims = (
            self
            ._decode_refresh_token_with_csrf(
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
            self
            .auth_session_repository
            .get_by_id(
                claims.session_id
            )
        )

        if session is None:
            raise InvalidCredentialsError(
                "The authentication session "
                "does not exist."
            )

        now = datetime.now(
            timezone.utc
        )

        self._require_usable_session(
            session=session,
            claims=claims,
            now=now,
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
            user=user,
            session=session,
            claims=claims,
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
        Atomically consume one refresh credential and issue
        its replacement.
        """

        claims = (
            self
            ._decode_refresh_token_with_csrf(
                token,
                csrf_cookie=(
                    csrf_cookie
                ),
                csrf_header=(
                    csrf_header
                ),
            )
        )

        # Lock the persistent session before checking and
        # replacing current_jti.
        session = (
            self
            .auth_session_repository
            .get_by_id_for_update(
                claims.session_id
            )
        )

        if session is None:
            raise InvalidCredentialsError(
                "The authentication session "
                "does not exist."
            )

        now = datetime.now(
            timezone.utc
        )

        self._require_usable_session(
            session=session,
            claims=claims,
            now=now,
        )

        # -------------------------------------------------
        # REFRESH-TOKEN REUSE DETECTION
        # -------------------------------------------------

        if (
            session.current_jti
            != claims.token_id
        ):
            self.auth_session_repository.revoke(
                session_id=(
                    session.id
                ),
                revoked_at=now,
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
            last_used_at=now,
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
            user=user,
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
    # CURRENT-SESSION REVOCATION
    # =====================================================

    def revoke_refresh_session_with_csrf(
        self,
        token: str,
        *,
        csrf_cookie: str | None,
        csrf_header: str | None,
    ) -> SessionRevocationResult:
        """
        Validate and revoke the persistent session represented
        by the supplied refresh credential.

        This method backs POST /auth/logout.

        The session row is locked so refresh and logout cannot
        concurrently mutate the same session without
        serialization.
        """

        claims = (
            self
            ._decode_refresh_token_with_csrf(
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
            self
            .auth_session_repository
            .get_by_id_for_update(
                claims.session_id
            )
        )

        if session is None:
            raise InvalidCredentialsError(
                "The authentication session "
                "does not exist."
            )

        now = datetime.now(
            timezone.utc
        )

        self._require_usable_session(
            session=session,
            claims=claims,
            now=now,
        )

        # A stale but otherwise validly signed refresh token
        # means that this token family has already advanced.
        #
        # Conservatively revoke the complete session rather
        # than leave a potentially compromised current token
        # active.
        if (
            session.current_jti
            != claims.token_id
        ):
            self.auth_session_repository.revoke(
                session_id=(
                    session.id
                ),
                revoked_at=now,
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
            revoked_at=now,
            reason="logout",
        )

        return SessionRevocationResult(
            user=user,
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
        Revoke every currently-unrevoked refresh session
        belonging to one user.

        This powers "logout everywhere".

        Existing short-lived access JWTs remain valid until
        their normal expiration because access tokens remain
        stateless.
        """

        self._require_active_user(
            user
        )

        now = datetime.now(
            timezone.utc
        )

        return (
            self
            .auth_session_repository
            .revoke_all_for_user(
                user_id=(
                    user.id
                ),
                revoked_at=now,
                reason=(
                    "logout_all"
                ),
            )
        )

    # =====================================================
    # REFRESH JWT + CSRF VALIDATION
    # =====================================================

    def _decode_refresh_token_with_csrf(
        self,
        token: str,
        *,
        csrf_cookie: str | None,
        csrf_header: str | None,
    ) -> RefreshTokenClaims:
        """
        Validate refresh-token cryptography and the
        session-bound CSRF proof.
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
    # PERSISTENT SESSION INVARIANTS
    # =====================================================

    @staticmethod
    def _require_usable_session(
        *,
        session: AuthSession,
        claims: RefreshTokenClaims,
        now: datetime,
    ) -> None:
        """
        Validate persistent-session invariants except
        current_jti.
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
        if (
            csrf_cookie is None
            or csrf_header is None
        ):
            raise InvalidCsrfTokenError(
                "CSRF proof is missing."
            )

        tokens_match = (
            hmac.compare_digest(
                csrf_cookie.encode(
                    "utf-8"
                ),
                csrf_header.encode(
                    "utf-8"
                ),
            )
        )

        if not tokens_match:
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
    # USER RESOLUTION
    # =====================================================

    def _resolve_active_user(
        self,
        user_id: UUID,
    ) -> User:
        user = (
            self.repository.get_by_id(
                user_id
            )
        )

        if user is None:
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
        if not user.is_active:
            raise InactiveUserError(
                "The user account is inactive."
            )