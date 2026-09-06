from dataclasses import dataclass
from uuid import UUID

from app.core.csrf import (
    create_csrf_token,
    validate_csrf_pair,
)

from app.core.security import (
    DUMMY_PASSWORD_HASH,
    TokenValidationError,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    verify_password,
)

from app.domain.user import User

from app.repositories.user_repository import (
    UserRepository,
)


# =========================================================
# AUTHENTICATION RESULT
# =========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class AuthenticationResult:
    """
    Internal authentication-service result.

    The refresh token and CSRF token are returned to the API
    layer so that FastAPI can place them into cookies.

    They are not intended to be serialized into the frontend
    JSON response.
    """

    access_token: str

    refresh_token: str

    csrf_token: str

    user: User


# =========================================================
# AUTHENTICATION EXCEPTIONS
# =========================================================


class AuthenticationError(Exception):
    """
    Base class for authentication-related failures.
    """

    pass


class InvalidCredentialsError(
    AuthenticationError
):
    """
    Raised when credentials or authentication tokens cannot
    be trusted.
    """

    pass


class InactiveUserError(
    AuthenticationError
):
    """
    Raised when an authenticated user exists but has been
    disabled.
    """

    pass


class InvalidCsrfTokenError(
    AuthenticationError
):
    """
    Raised when CSRF validation fails for a
    cookie-authenticated request.
    """

    pass


# =========================================================
# AUTHENTICATION SERVICE
# =========================================================


class AuthenticationService:
    def __init__(
        self,
        repository: UserRepository,
    ) -> None:
        self.repository = repository

    # -----------------------------------------------------
    # Username/password authentication
    # -----------------------------------------------------

    def authenticate(
        self,
        *,
        email: str,
        password: str,
    ) -> User:
        """
        Authenticate an email/password pair.

        The email is normalized before repository lookup.

        A dummy password hash is verified when the account
        does not exist so the code performs similar password
        hashing work for nonexistent and existing accounts.
        """

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
            # Perform password hashing work anyway,
            # reducing username-enumeration timing
            # differences.
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

    # -----------------------------------------------------
    # Complete authentication-result issuance
    # -----------------------------------------------------

    def issue_authentication_result(
        self,
        user: User,
        *,
        csrf_token: str | None = None,
    ) -> AuthenticationResult:
        """
        Issue the complete credential set required by the API
        authentication layer.

        Login calls this without csrf_token, causing a new
        signed CSRF token to be generated.

        Refresh can supply the already validated CSRF token
        so the CSRF token remains stable for the lifetime of
        the current browser authentication session.
        """

        self._require_active_user(
            user
        )

        access_token = (
            self.issue_access_token(
                user
            )
        )

        refresh_token = (
            self.issue_refresh_token(
                user
            )
        )

        if csrf_token is None:
            csrf_token = (
                self.issue_csrf_token(
                    user
                )
            )

        return AuthenticationResult(
            access_token=access_token,
            refresh_token=refresh_token,
            csrf_token=csrf_token,
            user=user,
        )

    # -----------------------------------------------------
    # Access-token issuance
    # -----------------------------------------------------

    def issue_access_token(
        self,
        user: User,
    ) -> str:
        """
        Issue a short-lived bearer access token.
        """

        self._require_active_user(
            user
        )

        return create_access_token(
            user.id
        )

    # -----------------------------------------------------
    # Refresh-token issuance
    # -----------------------------------------------------

    def issue_refresh_token(
        self,
        user: User,
    ) -> str:
        """
        Issue the refresh JWT that will be placed into the
        browser's HttpOnly refresh cookie.
        """

        self._require_active_user(
            user
        )

        return create_refresh_token(
            user.id
        )

    # -----------------------------------------------------
    # CSRF-token issuance
    # -----------------------------------------------------

    def issue_csrf_token(
        self,
        user: User,
    ) -> str:
        """
        Issue a signed CSRF token associated with the
        authenticated identity.

        The current authentication service resolves refresh
        JWTs directly to user UUIDs and does not yet expose a
        persistent AuthSession.sid.

        Therefore the CSRF token is currently bound to the
        authenticated user's UUID.

        If AuthSession.sid becomes part of this service
        later, this binding can move from user.id to
        session.id without changing the browser protocol.
        """

        self._require_active_user(
            user
        )

        return create_csrf_token(
            str(user.id)
        )

    # -----------------------------------------------------
    # Access-token resolution
    # -----------------------------------------------------

    def resolve_access_token(
        self,
        token: str,
    ) -> User:
        """
        Validate an access JWT and resolve its active user.
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

        return self._resolve_active_user(
            user_id
        )

    # -----------------------------------------------------
    # Refresh-token resolution
    # -----------------------------------------------------

    def resolve_refresh_token(
        self,
        token: str,
    ) -> User:
        """
        Validate a refresh JWT and resolve its active user.

        This method validates the refresh credential only.

        Cookie-authenticated API routes should normally call
        resolve_refresh_token_with_csrf() instead.
        """

        try:
            user_id = (
                decode_refresh_token(
                    token
                )
            )

        except TokenValidationError as exc:
            raise InvalidCredentialsError(
                "Invalid refresh token."
            ) from exc

        return self._resolve_active_user(
            user_id
        )

    # -----------------------------------------------------
    # Refresh-token + CSRF resolution
    # -----------------------------------------------------

    def resolve_refresh_token_with_csrf(
        self,
        token: str,
        *,
        csrf_cookie: str | None,
        csrf_header: str | None,
    ) -> User:
        """
        Validate a cookie-authenticated request.

        The refresh JWT establishes the authenticated
        identity.

        The CSRF cookie/header pair demonstrates that the
        request was deliberately initiated by the trusted
        frontend instead of merely causing the browser to
        send its cookies automatically.
        """

        user = (
            self.resolve_refresh_token(
                token
            )
        )

        csrf_is_valid = (
            validate_csrf_pair(
                cookie_token=csrf_cookie,
                header_token=csrf_header,
                session_id=str(user.id),
            )
        )

        if not csrf_is_valid:
            raise InvalidCsrfTokenError(
                "CSRF validation failed."
            )

        return user

    # -----------------------------------------------------
    # Shared user validation
    # -----------------------------------------------------

    def _resolve_active_user(
        self,
        user_id: UUID,
    ) -> User:
        """
        Resolve an authenticated user UUID and enforce active
        account state.
        """

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

    # -----------------------------------------------------
    # Shared active-user validation
    # -----------------------------------------------------

    @staticmethod
    def _require_active_user(
        user: User,
    ) -> None:
        """
        Reject authentication operations for inactive users.
        """

        if not user.is_active:
            raise InactiveUserError(
                "The user account is inactive."
            )