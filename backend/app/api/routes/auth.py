import logging
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)

from fastapi.responses import (
    JSONResponse,
)

from fastapi.security import (
    OAuth2PasswordRequestForm,
)

from app.api.dependencies import (
    CurrentUser,
    LoginThrottleDependency,
    get_authentication_service,
)

from app.core.auth_cookies import (
    clear_refresh_cookie,
    get_refresh_cookie,
    prevent_auth_response_caching,
    set_refresh_cookie,
)

from app.core.config import (
    settings,
)

from app.core.security_events import (
    security_event_logger,
)

from app.schemas.auth import (
    TokenResponse,
)

from app.schemas.user import (
    UserRead,
)

from app.services.authentication_service import (
    AuthenticationError,
    AuthenticationService,
    InvalidCsrfTokenError,
    RefreshTokenReuseError,
)


router = APIRouter()


# =========================================================
# SHARED HTTP EXCEPTIONS
# =========================================================


def _credentials_exception(
    detail: str,
) -> HTTPException:
    """
    Create the standard HTTP 401 response used when
    authentication credentials cannot be trusted.
    """

    return HTTPException(
        status_code=(
            status.HTTP_401_UNAUTHORIZED
        ),
        detail=detail,
        headers={
            "WWW-Authenticate": (
                "Bearer"
            ),
            "Cache-Control": (
                "no-store"
            ),
            "Pragma": (
                "no-cache"
            ),
        },
    )


def _csrf_exception() -> HTTPException:
    """
    CSRF validation failures are authorization failures.

    The client receives a generic HTTP 403 response rather
    than internal validation details.
    """

    return HTTPException(
        status_code=(
            status.HTTP_403_FORBIDDEN
        ),
        detail=(
            "CSRF validation failed."
        ),
        headers={
            "Cache-Control": (
                "no-store"
            ),
            "Pragma": (
                "no-cache"
            ),
        },
    )


# =========================================================
# CSRF REQUEST HELPERS
# =========================================================


def _get_csrf_cookie(
    request: Request,
) -> str | None:
    """
    Read the JavaScript-readable CSRF cookie.
    """

    return request.cookies.get(
        settings.csrf_cookie_name
    )


def _get_csrf_header(
    request: Request,
) -> str | None:
    """
    Read the CSRF proof copied by the frontend into the
    configured request header.
    """

    return request.headers.get(
        settings.csrf_header_name
    )


# =========================================================
# CSRF COOKIE HELPERS
# =========================================================


def _set_csrf_cookie(
    response: Response,
    csrf_token: str,
) -> None:
    """
    Set the JavaScript-readable signed CSRF cookie.

    httponly=False is intentional because the frontend must
    read the value and copy it into X-CSRF-Token.
    """

    response.set_cookie(
        key=(
            settings.csrf_cookie_name
        ),
        value=csrf_token,
        httponly=False,
        secure=(
            settings.is_production
        ),
        samesite=(
            settings.refresh_cookie_samesite
        ),
        path="/",
    )


def _clear_csrf_cookie(
    response: Response,
) -> None:
    """
    Expire the CSRF cookie.
    """

    response.delete_cookie(
        key=(
            settings.csrf_cookie_name
        ),
        path="/",
    )


def _clear_auth_cookies(
    response: Response,
) -> None:
    """
    Clear both browser-managed authentication cookies.
    """

    clear_refresh_cookie(
        response
    )

    _clear_csrf_cookie(
        response
    )


# =========================================================
# LOGIN
# =========================================================


@router.post(
    "/token",
    response_model=TokenResponse,
    status_code=(
        status.HTTP_200_OK
    ),
)
def login_for_access_token(
    request: Request,
    response: Response,
    form_data: Annotated[
        OAuth2PasswordRequestForm,
        Depends(),
    ],
    authentication_service: Annotated[
        AuthenticationService,
        Depends(
            get_authentication_service
        ),
    ],
    login_throttle: (
        LoginThrottleDependency
    ),
) -> TokenResponse:
    """
    Authenticate username/password credentials and establish
    a new persistent browser authentication session.

    A successful login creates:

        auth_sessions row

        access JWT

        HttpOnly refresh JWT

        session-bound readable CSRF cookie
    """

    # =====================================================
    # SOURCE ADDRESS
    # =====================================================

    client_address = (
        request.client.host
        if request.client is not None
        else "unknown"
    )

    # =====================================================
    # LOGIN THROTTLING
    # =====================================================

    throttle_decision = (
        login_throttle.begin_attempt(
            client_address=(
                client_address
            ),
            account_identifier=(
                form_data.username
            ),
        )
    )

    if not throttle_decision.allowed:
        security_event_logger.emit(
            event=(
                "auth.login.throttled"
            ),
            outcome="blocked",
            level=logging.WARNING,
            request=request,
            account_identifier=(
                form_data.username
            ),
            reason=(
                throttle_decision.blocked_by
                or "unknown"
            ),
        )

        raise HTTPException(
            status_code=(
                status
                .HTTP_429_TOO_MANY_REQUESTS
            ),
            detail=(
                "Too many authentication "
                "attempts. Please try again later."
            ),
            headers={
                "Cache-Control": (
                    "no-store"
                ),
                "Pragma": (
                    "no-cache"
                ),
            },
        )

    # =====================================================
    # PASSWORD AUTHENTICATION
    # =====================================================

    try:
        user = (
            authentication_service
            .authenticate(
                email=(
                    form_data.username
                ),
                password=(
                    form_data.password
                ),
            )
        )

    except AuthenticationError as exc:
        login_throttle.record_failure(
            account_identifier=(
                form_data.username
            )
        )

        security_event_logger.emit(
            event=(
                "auth.login.failed"
            ),
            outcome="failure",
            level=logging.WARNING,
            request=request,
            account_identifier=(
                form_data.username
            ),
            reason=(
                "invalid_credentials"
            ),
        )

        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Incorrect email or password."
            ),
            headers={
                "WWW-Authenticate": (
                    "Bearer"
                ),
                "Cache-Control": (
                    "no-store"
                ),
                "Pragma": (
                    "no-cache"
                ),
            },
        ) from exc

    # =====================================================
    # SUCCESS
    # =====================================================

    login_throttle.record_success(
        account_identifier=(
            form_data.username
        )
    )

    result = (
        authentication_service
        .issue_authentication_result(
            user
        )
    )

    # Store refresh credential only in the HttpOnly browser
    # cookie.
    set_refresh_cookie(
        response,
        result.refresh_token,
    )

    # Store the session-bound CSRF proof separately.
    _set_csrf_cookie(
        response,
        result.csrf_token,
    )

    security_event_logger.emit(
        event=(
            "auth.login.succeeded"
        ),
        outcome="success",
        level=logging.INFO,
        request=request,
        user_id=(
            user.id
        ),
    )

    prevent_auth_response_caching(
        response
    )

    # Only the short-lived access JWT is returned in JSON.
    return TokenResponse(
        access_token=(
            result.access_token
        ),
    )


# =========================================================
# REFRESH
# =========================================================


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=(
        status.HTTP_200_OK
    ),
)
def refresh_access_token(
    request: Request,
    response: Response,
    authentication_service: Annotated[
        AuthenticationService,
        Depends(
            get_authentication_service
        ),
    ],
) -> TokenResponse | Response:
    """
    Atomically consume the currently-valid refresh JWT and
    replace it with another refresh JWT.

    Phase 6.4C-3 refresh sequence:

        refresh JWT
            +
        matching CSRF cookie/header
            +
        persistent session
            +
        SELECT ... FOR UPDATE
            +
        JWT jti == auth_sessions.current_jti
            |
            v
        rotate current_jti
            |
            v
        return new access JWT
        set new refresh cookie

    If an already-consumed refresh JWT is submitted again,
    the entire authentication session is revoked.
    """

    # =====================================================
    # READ REFRESH CREDENTIAL
    # =====================================================

    refresh_token = (
        get_refresh_cookie(
            request
        )
    )

    if refresh_token is None:
        security_event_logger.emit(
            event=(
                "auth.refresh.failed"
            ),
            outcome="failure",
            level=logging.WARNING,
            request=request,
            reason=(
                "missing_refresh_cookie"
            ),
        )

        raise _credentials_exception(
            "Could not refresh credentials."
        )

    # =====================================================
    # READ CSRF PROOF
    # =====================================================

    csrf_cookie = (
        _get_csrf_cookie(
            request
        )
    )

    csrf_header = (
        _get_csrf_header(
            request
        )
    )

    # =====================================================
    # ATOMIC REFRESH ROTATION
    # =====================================================

    try:
        rotation_result = (
            authentication_service
            .rotate_refresh_token_with_csrf(
                refresh_token,
                csrf_cookie=(
                    csrf_cookie
                ),
                csrf_header=(
                    csrf_header
                ),
            )
        )

    # =====================================================
    # CSRF FAILURE
    # =====================================================

    except InvalidCsrfTokenError as exc:
        # Do not clear legitimate authentication cookies
        # merely because an unsafe request failed CSRF
        # validation.
        security_event_logger.emit(
            event=(
                "csrf.validation.failed"
            ),
            outcome="blocked",
            level=logging.WARNING,
            request=request,
            reason=(
                "refresh_request"
            ),
        )

        raise _csrf_exception() from exc

    # =====================================================
    # REFRESH-TOKEN REUSE
    # =====================================================

    except RefreshTokenReuseError as exc:
        # rotate_refresh_token_with_csrf() has already
        # revoked this persistent auth session.
        #
        # IMPORTANT:
        #
        # Return a concrete Response instead of allowing the
        # reuse exception to propagate through the database
        # dependency.
        #
        # The revocation must survive the rejected HTTP
        # request rather than being rolled back.
        security_event_logger.emit(
            event=(
                "auth.refresh.reuse_detected"
            ),
            outcome="blocked",
            level=logging.WARNING,
            request=request,
            user_id=(
                exc.user_id
            ),
            reason=(
                "refresh_token_reuse"
            ),
        )

        replay_response = JSONResponse(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            content={
                "detail": (
                    "Could not refresh "
                    "credentials."
                )
            },
            headers={
                "WWW-Authenticate": (
                    "Bearer"
                ),
                "Cache-Control": (
                    "no-store"
                ),
                "Pragma": (
                    "no-cache"
                ),
            },
        )

        # The browser's refresh credential belongs to a
        # revoked token family and must be removed.
        _clear_auth_cookies(
            replay_response
        )

        return replay_response

    # =====================================================
    # OTHER REFRESH FAILURE
    # =====================================================

    except AuthenticationError as exc:
        security_event_logger.emit(
            event=(
                "auth.refresh.failed"
            ),
            outcome="failure",
            level=logging.WARNING,
            request=request,
            reason=(
                "invalid_refresh_credential"
            ),
        )

        raise _credentials_exception(
            "Could not refresh credentials."
        ) from exc

    # =====================================================
    # SUCCESSFUL ROTATION
    # =====================================================

    # The server-side session ID remains constant.
    #
    # Only current_jti changes.
    #
    # Store the new refresh JWT in the same HttpOnly cookie.
    set_refresh_cookie(
        response,
        rotation_result.refresh_token,
    )

    # =====================================================
    # KEEP CSRF COOKIE STABLE
    # =====================================================

    # The CSRF proof is bound to the persistent session ID
    # rather than to the refresh token's jti.
    #
    # Therefore:
    #
    #   sid stays S1
    #
    #   J1 -> J2 -> J3
    #
    # while the existing CSRF token remains valid.
    #
    # Do not call _set_csrf_cookie() here.

    security_event_logger.emit(
        event=(
            "auth.refresh.succeeded"
        ),
        outcome="success",
        level=logging.INFO,
        request=request,
        user_id=(
            rotation_result
            .user
            .id
        ),
        details={
            "refresh_rotated": True,
        },
    )

    prevent_auth_response_caching(
        response
    )

    return TokenResponse(
        access_token=(
            rotation_result
            .access_token
        ),
    )


# =========================================================
# LOGOUT
# =========================================================


@router.post(
    "/logout",
    status_code=(
        status.HTTP_204_NO_CONTENT
    ),
)
def logout(
    request: Request,
    response: Response,
    authentication_service: Annotated[
        AuthenticationService,
        Depends(
            get_authentication_service
        ),
    ],
) -> None:
    """
    Revoke the current persistent refresh session and remove
    browser authentication state.

    Logout remains idempotent:

        no refresh cookie
            -> clear stale cookies
            -> 204

        valid refresh + valid CSRF
            -> revoke server session
            -> clear cookies
            -> 204

        bad CSRF
            -> preserve legitimate cookies
            -> 403

        invalid/already-revoked session
            -> clear stale cookies
            -> 204

        stale refresh-token replay
            -> revoke token family
            -> clear cookies
            -> 204
    """

    # =====================================================
    # READ REFRESH CREDENTIAL
    # =====================================================

    refresh_token = (
        get_refresh_cookie(
            request
        )
    )

    # =====================================================
    # ALREADY LOGGED OUT
    # =====================================================

    if refresh_token is None:
        _clear_auth_cookies(
            response
        )

        prevent_auth_response_caching(
            response
        )

        return

    # =====================================================
    # READ CSRF PROOF
    # =====================================================

    csrf_cookie = (
        _get_csrf_cookie(
            request
        )
    )

    csrf_header = (
        _get_csrf_header(
            request
        )
    )

    # =====================================================
    # SERVER-SIDE SESSION REVOCATION
    # =====================================================

    try:
        revocation_result = (
            authentication_service
            .revoke_refresh_session_with_csrf(
                refresh_token,
                csrf_cookie=(
                    csrf_cookie
                ),
                csrf_header=(
                    csrf_header
                ),
            )
        )

    # =====================================================
    # CSRF FAILURE
    # =====================================================

    except InvalidCsrfTokenError as exc:
        security_event_logger.emit(
            event=(
                "csrf.validation.failed"
            ),
            outcome="blocked",
            level=logging.WARNING,
            request=request,
            reason=(
                "logout_request"
            ),
        )

        # Invalid CSRF must not destroy an otherwise-valid
        # browser session.
        raise _csrf_exception() from exc

    # =====================================================
    # REFRESH-TOKEN REUSE
    # =====================================================

    except RefreshTokenReuseError as exc:
        # The authentication service has already revoked the
        # refresh-token family.
        #
        # Logout itself remains idempotently successful.
        security_event_logger.emit(
            event=(
                "auth.logout.reuse_detected"
            ),
            outcome="blocked",
            level=logging.WARNING,
            request=request,
            user_id=(
                exc.user_id
            ),
            reason=(
                "refresh_token_reuse"
            ),
        )

        _clear_auth_cookies(
            response
        )

        prevent_auth_response_caching(
            response
        )

        return

    # =====================================================
    # INVALID / ALREADY-REVOKED SESSION
    # =====================================================

    except AuthenticationError:
        security_event_logger.emit(
            event=(
                "auth.logout.stale_session"
            ),
            outcome="success",
            level=logging.INFO,
            request=request,
            reason=(
                "invalid_refresh_credential"
            ),
        )

        _clear_auth_cookies(
            response
        )

        prevent_auth_response_caching(
            response
        )

        return

    # =====================================================
    # SUCCESSFUL LOGOUT
    # =====================================================

    _clear_auth_cookies(
        response
    )

    prevent_auth_response_caching(
        response
    )

    security_event_logger.emit(
        event=(
            "auth.logout.succeeded"
        ),
        outcome="success",
        level=logging.INFO,
        request=request,

        # C-4 correction:
        #
        # revoke_refresh_session_with_csrf() returns
        # SessionRevocationResult, not ResolvedRefreshSession.
        user_id=(
            revocation_result
            .user
            .id
        ),

        details={
            "session_revoked": True,
        },
    )
    
    
# =========================================================
# LOGOUT ALL
# =========================================================


@router.post(
    "/logout-all",
    status_code=(
        status.HTTP_204_NO_CONTENT
    ),
)
def logout_all(
    request: Request,
    response: Response,
    current_user: CurrentUser,
    authentication_service: Annotated[
        AuthenticationService,
        Depends(
            get_authentication_service
        ),
    ],
) -> None:
    """
    Revoke every persistent refresh session belonging to the
    currently bearer-authenticated user.

    Unlike ordinary /logout, this endpoint is authenticated
    with the short-lived access token in the Authorization
    header.

    Browsers do not automatically attach bearer tokens, so
    this operation does not depend on refresh-cookie CSRF
    authentication.
    """

    # =====================================================
    # REVOKE ALL SERVER-SIDE SESSIONS
    # =====================================================

    revoked_count = (
        authentication_service
        .revoke_all_sessions_for_user(
            current_user
        )
    )

    # =====================================================
    # CLEAR THIS BROWSER'S AUTHENTICATION COOKIES
    # =====================================================

    # Other devices cannot have their cookies remotely
    # deleted, but their corresponding server-side sessions
    # are now revoked and therefore cannot refresh again.
    _clear_auth_cookies(
        response
    )

    prevent_auth_response_caching(
        response
    )

    # =====================================================
    # SECURITY AUDIT EVENT
    # =====================================================

    security_event_logger.emit(
        event=(
            "auth.logout_all.succeeded"
        ),
        outcome="success",
        level=logging.INFO,
        request=request,
        user_id=(
            current_user.id
        ),
        details={
            "sessions_revoked": (
                revoked_count
            ),
        },
    )


# =========================================================
# CURRENT USER
# =========================================================


@router.get(
    "/me",
    response_model=UserRead,
    status_code=(
        status.HTTP_200_OK
    ),
)
def read_current_user(
    current_user: CurrentUser,
) -> UserRead:
    """
    Return the current bearer-authenticated user.

    /me uses the Authorization header rather than
    cookie-managed authentication state, so CSRF validation
    is not required.
    """

    return UserRead.model_validate(
        current_user
    )