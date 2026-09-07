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
    PasswordChangeRequest,
    ReauthenticationRequest,
    ReauthenticationResponse,
    TokenResponse,
)

from app.schemas.user import (
    UserRead,
)

from app.services.authentication_service import (
    AuthenticationError,
    AuthenticationService,
    InvalidCsrfTokenError,
    PasswordChangeError,
    ReauthenticationError,
    RefreshTokenReuseError,
)


router = APIRouter()


# =========================================================
# SHARED HTTP EXCEPTIONS
# =========================================================


def _credentials_exception(
    detail: str,
) -> HTTPException:
    return HTTPException(
        status_code=(
            status
            .HTTP_401_UNAUTHORIZED
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


def _csrf_exception(
) -> HTTPException:
    return HTTPException(
        status_code=(
            status
            .HTTP_403_FORBIDDEN
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


def _reauthentication_exception(
) -> HTTPException:
    return HTTPException(
        status_code=(
            status
            .HTTP_403_FORBIDDEN
        ),
        detail=(
            "Valid recent reauthentication "
            "is required."
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
# CSRF HELPERS
# =========================================================


def _get_csrf_cookie(
    request: Request,
) -> str | None:
    return request.cookies.get(
        settings.csrf_cookie_name
    )


def _get_csrf_header(
    request: Request,
) -> str | None:
    return request.headers.get(
        settings.csrf_header_name
    )


def _set_csrf_cookie(
    response: Response,
    csrf_token: str,
) -> None:
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
            settings
            .refresh_cookie_samesite
        ),
        path="/",
    )


def _clear_csrf_cookie(
    response: Response,
) -> None:
    response.delete_cookie(
        key=(
            settings.csrf_cookie_name
        ),
        path="/",
    )


def _clear_auth_cookies(
    response: Response,
) -> None:
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
    client_address = (
        request.client.host
        if request.client is not None
        else "unknown"
    )

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
                throttle_decision
                .blocked_by
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
                status
                .HTTP_401_UNAUTHORIZED
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

    set_refresh_cookie(
        response,
        result.refresh_token,
    )

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

    return TokenResponse(
        access_token=(
            result.access_token
        ),
    )


# =========================================================
# REAUTHENTICATION
# =========================================================


@router.post(
    "/reauthenticate",
    response_model=(
        ReauthenticationResponse
    ),
    status_code=(
        status.HTTP_200_OK
    ),
)
def reauthenticate_current_user(
    request: Request,
    response: Response,
    payload: ReauthenticationRequest,
    current_user: CurrentUser,
    authentication_service: Annotated[
        AuthenticationService,
        Depends(
            get_authentication_service
        ),
    ],
) -> ReauthenticationResponse:
    try:
        result = (
            authentication_service
            .reauthenticate(
                current_user,
                password=(
                    payload
                    .password
                    .get_secret_value()
                ),
            )
        )

    except ReauthenticationError as exc:
        security_event_logger.emit(
            event=(
                "auth.reauthentication.failed"
            ),
            outcome="failure",
            level=logging.WARNING,
            request=request,
            user_id=(
                current_user.id
            ),
            reason=(
                "invalid_current_password"
            ),
        )

        raise HTTPException(
            status_code=(
                status
                .HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Reauthentication failed."
            ),
            headers={
                "Cache-Control": (
                    "no-store"
                ),
                "Pragma": (
                    "no-cache"
                ),
            },
        ) from exc

    security_event_logger.emit(
        event=(
            "auth.reauthentication.succeeded"
        ),
        outcome="success",
        level=logging.INFO,
        request=request,
        user_id=(
            current_user.id
        ),
    )

    prevent_auth_response_caching(
        response
    )

    return ReauthenticationResponse(
        reauth_token=(
            result.reauth_token
        ),
        expires_in_seconds=(
            result
            .expires_in_seconds
        ),
    )


# =========================================================
# CHANGE PASSWORD
# =========================================================


@router.post(
    "/change-password",
    status_code=(
        status.HTTP_204_NO_CONTENT
    ),
)
def change_current_user_password(
    request: Request,
    response: Response,
    payload: PasswordChangeRequest,
    current_user: CurrentUser,
    authentication_service: Annotated[
        AuthenticationService,
        Depends(
            get_authentication_service
        ),
    ],
) -> None:
    """
    Change the authenticated user's password.

    This endpoint does not use the refresh cookie as its
    authentication mechanism.

    Required proof:

        bearer access JWT
            +
        recent reauthentication JWT
            +
        replacement password

    On success every persistent refresh session is revoked
    and this browser's authentication cookies are removed.
    """

    try:
        result = (
            authentication_service
            .change_password(
                current_user,
                reauth_token=(
                    payload
                    .reauth_token
                    .get_secret_value()
                ),
                new_password=(
                    payload
                    .new_password
                    .get_secret_value()
                ),
            )
        )

    except ReauthenticationError as exc:
        security_event_logger.emit(
            event=(
                "auth.password_change.blocked"
            ),
            outcome="blocked",
            level=logging.WARNING,
            request=request,
            user_id=(
                current_user.id
            ),
            reason=(
                "invalid_or_stale_reauthentication"
            ),
        )

        raise (
            _reauthentication_exception()
        ) from exc

    except PasswordChangeError as exc:
        security_event_logger.emit(
            event=(
                "auth.password_change.failed"
            ),
            outcome="failure",
            level=logging.WARNING,
            request=request,
            user_id=(
                current_user.id
            ),
            reason=(
                "password_policy_rejected"
            ),
        )

        raise HTTPException(
            status_code=(
                status
                .HTTP_400_BAD_REQUEST
            ),
            detail=str(
                exc
            ),
            headers={
                "Cache-Control": (
                    "no-store"
                ),
                "Pragma": (
                    "no-cache"
                ),
            },
        ) from exc

    # Password mutation and persistent-session revocation
    # have now succeeded in this request transaction.
    #
    # Remove this browser's cookie credentials as well.
    _clear_auth_cookies(
        response
    )

    prevent_auth_response_caching(
        response
    )

    security_event_logger.emit(
        event=(
            "auth.password_change.succeeded"
        ),
        outcome="success",
        level=logging.WARNING,
        request=request,
        user_id=(
            result.user_id
        ),
        details={
            "sessions_revoked": (
                result
                .revoked_sessions
            ),
        },
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

    except InvalidCsrfTokenError as exc:
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

    except RefreshTokenReuseError as exc:
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

        replay_response = (
            JSONResponse(
                status_code=(
                    status
                    .HTTP_401_UNAUTHORIZED
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
        )

        _clear_auth_cookies(
            replay_response
        )

        return replay_response

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

    set_refresh_cookie(
        response,
        rotation_result.refresh_token,
    )

    security_event_logger.emit(
        event=(
            "auth.refresh.succeeded"
        ),
        outcome="success",
        level=logging.INFO,
        request=request,
        user_id=(
            rotation_result.user.id
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
            rotation_result.access_token
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
    refresh_token = (
        get_refresh_cookie(
            request
        )
    )

    if refresh_token is None:
        _clear_auth_cookies(
            response
        )

        prevent_auth_response_caching(
            response
        )

        return

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

        raise _csrf_exception() from exc

    except RefreshTokenReuseError as exc:
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

    except AuthenticationError:
        _clear_auth_cookies(
            response
        )

        prevent_auth_response_caching(
            response
        )

        return

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
        user_id=(
            revocation_result.user.id
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
    revoked_count = (
        authentication_service
        .revoke_all_sessions_for_user(
            current_user
        )
    )

    _clear_auth_cookies(
        response
    )

    prevent_auth_response_caching(
        response
    )

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
    return UserRead.model_validate(
        current_user
    )