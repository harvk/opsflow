from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)

from fastapi.security import (
    OAuth2PasswordRequestForm,
)

from app.api.dependencies import (
    CurrentUser,
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
)


router = APIRouter()


# =========================================================
# SHARED HTTP EXCEPTIONS
# =========================================================


def _credentials_exception(
    detail: str,
) -> HTTPException:
    """
    Create the standard HTTP 401 response used for invalid
    authentication credentials.
    """

    return HTTPException(
        status_code=(
            status.HTTP_401_UNAUTHORIZED
        ),
        detail=detail,
    )


def _csrf_exception() -> HTTPException:
    """
    CSRF failure is authorization failure rather than
    ordinary credential failure.

    The appropriate response is therefore HTTP 403.
    """

    return HTTPException(
        status_code=(
            status.HTTP_403_FORBIDDEN
        ),
        detail=(
            "CSRF validation failed."
        ),
    )


# =========================================================
# CSRF REQUEST HELPERS
# =========================================================


def _get_csrf_cookie(
    request: Request,
) -> str | None:
    """
    Read the JavaScript-readable CSRF cookie.

    The configured cookie name comes from Settings rather
    than being duplicated here.
    """

    return request.cookies.get(
        settings.csrf_cookie_name
    )


def _get_csrf_header(
    request: Request,
) -> str | None:
    """
    Read the CSRF token deliberately copied into the request
    by the frontend.

    The configured header name comes from Settings.
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
    Set the signed CSRF token.

    httponly=False is intentional.

    Unlike the refresh JWT, the CSRF token is not an
    authentication credential. The frontend must be able to
    read it and copy it into X-CSRF-Token.

    Cookie security behavior is derived from application
    configuration:

        development:
            secure=False

        production:
            secure=True

    SameSite behavior follows the application's configured
    refresh-cookie policy.
    """

    response.set_cookie(
        key=(
            settings.csrf_cookie_name
        ),
        value=csrf_token,
        httponly=False,

        # Settings does not define cookie_secure.
        #
        # Instead, is_production is the existing source of
        # truth for whether cookies should require HTTPS.
        secure=(
            settings.is_production
        ),

        # Reuse the configured authentication-cookie
        # SameSite policy instead of hard-coding it.
        samesite=(
            settings.refresh_cookie_samesite
        ),

        # Keep the CSRF cookie visible to the frontend.
        #
        # Unlike the HttpOnly refresh cookie, JavaScript must
        # be able to read this cookie from the application.
        path="/",
    )


def _clear_csrf_cookie(
    response: Response,
) -> None:
    """
    Expire the CSRF cookie.

    Cookie deletion must use the same path used when the
    cookie was created.
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

    The refresh-cookie helper owns the refresh-cookie
    configuration.

    This route module owns the JavaScript-readable CSRF
    cookie.
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
) -> TokenResponse:
    """
    Authenticate the user and establish browser
    authentication state.

    JSON response:
        access token

    Browser cookies:
        HttpOnly refresh token
        readable signed CSRF token
    """

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
                )
            },
        ) from exc

    result = (
        authentication_service
        .issue_authentication_result(
            user
        )
    )

    # -----------------------------------------------------
    # Refresh JWT
    # -----------------------------------------------------
    #
    # The refresh-cookie helper owns:
    #
    #   cookie name
    #   HttpOnly
    #   Secure
    #   SameSite
    #   Path
    #
    # JavaScript cannot read this credential.

    set_refresh_cookie(
        response,
        result.refresh_token,
    )

    # -----------------------------------------------------
    # CSRF token
    # -----------------------------------------------------
    #
    # This cookie is intentionally readable by JavaScript.
    #
    # apiClient.ts copies its value into the configured
    # X-CSRF-Token header for unsafe requests.

    _set_csrf_cookie(
        response,
        result.csrf_token,
    )

    prevent_auth_response_caching(
        response
    )

    # Only the short-lived access JWT crosses the JSON
    # boundary into React.
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
) -> TokenResponse:
    """
    Exchange the HttpOnly refresh credential for a new
    access token.

    Successful refresh requires:

        refresh cookie
        +
        CSRF cookie
        +
        configured CSRF header
    """

    refresh_token = (
        get_refresh_cookie(
            request
        )
    )

    if refresh_token is None:
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
        user = (
            authentication_service
            .resolve_refresh_token_with_csrf(
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
        # Important:
        #
        # Do not delete authentication cookies here.
        #
        # Otherwise a forged request with invalid CSRF proof
        # could potentially force a legitimate user's
        # browser out of its authenticated state.
        raise _csrf_exception() from exc

    except AuthenticationError as exc:
        # The refresh credential itself cannot be trusted.
        #
        # Remove both browser authentication cookies so the
        # browser does not repeatedly submit invalid state.
        _clear_auth_cookies(
            response
        )

        raise _credentials_exception(
            "Could not refresh credentials."
        ) from exc

    # Successful CSRF validation guarantees that the cookie
    # existed and was valid.
    assert csrf_cookie is not None

    result = (
        authentication_service
        .issue_authentication_result(
            user,
            csrf_token=(
                csrf_cookie
            ),
        )
    )

    # -----------------------------------------------------
    # Rotate refresh credential
    # -----------------------------------------------------

    set_refresh_cookie(
        response,
        result.refresh_token,
    )

    # -----------------------------------------------------
    # Preserve validated CSRF token
    # -----------------------------------------------------
    #
    # The CSRF token remains stable across this refresh
    # operation while the refresh JWT is replaced.

    _set_csrf_cookie(
        response,
        result.csrf_token,
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
    End browser authentication state.

    Logout remains idempotent:

        no refresh cookie
            -> clear stale cookies
            -> 204

        valid refresh + valid CSRF
            -> clear cookies
            -> 204

        invalid CSRF
            -> preserve legitimate cookies
            -> 403

        invalid refresh credential
            -> clear stale cookies
            -> 204
    """

    refresh_token = (
        get_refresh_cookie(
            request
        )
    )

    if refresh_token is None:
        # No refresh credential means the browser is already
        # effectively logged out.
        #
        # Clear any stale CSRF state and succeed.
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
        authentication_service.resolve_refresh_token_with_csrf(
            refresh_token,
            csrf_cookie=(
                csrf_cookie
            ),
            csrf_header=(
                csrf_header
            ),
        )

    except InvalidCsrfTokenError as exc:
        # Do not clear legitimate cookies when the request
        # itself fails CSRF validation.
        raise _csrf_exception() from exc

    except AuthenticationError:
        # The refresh credential is already unusable.
        #
        # Logout is idempotent, so remove stale browser
        # authentication state and finish successfully.
        _clear_auth_cookies(
            response
        )

        prevent_auth_response_caching(
            response
        )

        return

    # The request was authenticated and passed CSRF
    # validation.
    _clear_auth_cookies(
        response
    )

    prevent_auth_response_caching(
        response
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

    /me relies on the Authorization header rather than
    cookie authentication, so CSRF validation is not
    required.
    """

    return UserRead.model_validate(
        current_user
    )