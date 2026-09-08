import logging

from typing import (
    Annotated,
)

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
    PasswordResetDeliveryCoordinatorDependency,
    PasswordResetServiceDependency,
    PasswordResetThrottleDependency,
    get_authentication_service,
)

from app.core.auth_cookies import (
    clear_auth_cookies,
    get_csrf_cookie,
    get_refresh_cookie,
    set_csrf_cookie,
    set_refresh_cookie,
)

from app.core.auth_error_codes import (
    AuthErrorCode,
    auth_error_headers,
)

from app.core.auth_response_messages import (
    CSRF_VALIDATION_FAILED_MESSAGE,
    LOGIN_CREDENTIALS_INVALID_MESSAGE,
    LOGIN_THROTTLED_MESSAGE,
    PASSWORD_CHANGE_REJECTED_MESSAGE,
    PASSWORD_RESET_CREDENTIAL_INVALID_MESSAGE,
    PASSWORD_RESET_PASSWORD_REJECTED_MESSAGE,
    PASSWORD_RESET_THROTTLED_MESSAGE,
    REAUTHENTICATION_FAILED_MESSAGE,
    REAUTHENTICATION_REQUIRED_MESSAGE,
    REFRESH_CREDENTIALS_INVALID_MESSAGE,
)

from app.core.config import (
    settings,
)

from app.core.password_reset_messages import (
    PASSWORD_RESET_REQUEST_ACCEPTED_MESSAGE,
)

from app.core.security_events import (
    security_event_logger,
)

from app.schemas.auth import (
    PasswordChangeRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PasswordResetRequestResponse,
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

from app.services.password_reset_delivery import (
    PasswordResetDeliveryError,
)

from app.services.password_reset_service import (
    InvalidPasswordResetCredentialError,
    PasswordResetPasswordError,
)


router = (
    APIRouter()
)


# =========================================================
# SHARED HTTP EXCEPTIONS
# =========================================================


def _refresh_credentials_exception(
) -> HTTPException:
    return HTTPException(
        status_code=(
            status
            .HTTP_401_UNAUTHORIZED
        ),
        detail=(
            REFRESH_CREDENTIALS_INVALID_MESSAGE
        ),
        headers=(
            auth_error_headers(
                AuthErrorCode
                .REFRESH_CREDENTIALS_INVALID,
                additional_headers={
                    "WWW-Authenticate": (
                        "Bearer"
                    ),
                },
            )
        ),
    )


def _csrf_exception(
) -> HTTPException:
    return HTTPException(
        status_code=(
            status
            .HTTP_403_FORBIDDEN
        ),
        detail=(
            CSRF_VALIDATION_FAILED_MESSAGE
        ),
        headers=(
            auth_error_headers(
                AuthErrorCode
                .CSRF_VALIDATION_FAILED
            )
        ),
    )


def _reauthentication_exception(
) -> HTTPException:
    return HTTPException(
        status_code=(
            status
            .HTTP_403_FORBIDDEN
        ),
        detail=(
            REAUTHENTICATION_REQUIRED_MESSAGE
        ),
        headers=(
            auth_error_headers(
                AuthErrorCode
                .REAUTHENTICATION_REQUIRED
            )
        ),
    )


# =========================================================
# CSRF HELPERS
# =========================================================


def _get_csrf_header(
    request: Request,
) -> str | None:
    return request.headers.get(
        settings.csrf_header_name
    )


# =========================================================
# LOGIN
# =========================================================


@router.post(
    "/token",
    response_model=(
        TokenResponse
    ),
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
                LOGIN_THROTTLED_MESSAGE
            ),
            headers=(
                auth_error_headers(
                    AuthErrorCode
                    .LOGIN_THROTTLED
                )
            ),
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
                LOGIN_CREDENTIALS_INVALID_MESSAGE
            ),
            headers=(
                auth_error_headers(
                    AuthErrorCode
                    .LOGIN_CREDENTIALS_INVALID,
                    additional_headers={
                        "WWW-Authenticate": (
                            "Bearer"
                        ),
                    },
                )
            ),
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

    set_csrf_cookie(
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
                REAUTHENTICATION_FAILED_MESSAGE
            ),
            headers=(
                auth_error_headers(
                    AuthErrorCode
                    .REAUTHENTICATION_FAILED
                )
            ),
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
            detail=(
                PASSWORD_CHANGE_REJECTED_MESSAGE
            ),
            headers=(
                auth_error_headers(
                    AuthErrorCode
                    .PASSWORD_CHANGE_REJECTED
                )
            ),
        ) from exc

    clear_auth_cookies(
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
# PASSWORD RESET REQUEST
# =========================================================


@router.post(
    "/password-reset/request",
    response_model=(
        PasswordResetRequestResponse
    ),
    status_code=(
        status.HTTP_202_ACCEPTED
    ),
)
def request_password_reset(
    request: Request,
    response: Response,
    payload: PasswordResetRequest,
    password_reset_service: (
        PasswordResetServiceDependency
    ),
    password_reset_throttle: (
        PasswordResetThrottleDependency
    ),
    password_reset_delivery_coordinator: (
        PasswordResetDeliveryCoordinatorDependency
    ),
) -> PasswordResetRequestResponse:
    client_address = (
        request.client.host
        if request.client is not None
        else "unknown"
    )

    throttle_decision = (
        password_reset_throttle
        .check_and_record(
            client_address=(
                client_address
            ),
            account_identifier=(
                payload.email
            ),
        )
    )

    if not throttle_decision.allowed:
        security_event_logger.emit(
            event=(
                "auth.password_reset.throttled"
            ),
            outcome="blocked",
            level=logging.WARNING,
            request=request,
            account_identifier=(
                payload.email
            ),
            reason=(
                throttle_decision
                .blocked_by
                or "unknown"
            ),
            details={
                "retry_after_seconds": (
                    throttle_decision
                    .retry_after_seconds
                ),
            },
        )

        raise HTTPException(
            status_code=(
                status
                .HTTP_429_TOO_MANY_REQUESTS
            ),
            detail=(
                PASSWORD_RESET_THROTTLED_MESSAGE
            ),
            headers=(
                auth_error_headers(
                    AuthErrorCode
                    .PASSWORD_RESET_THROTTLED,
                    additional_headers={
                        "Retry-After": str(
                            throttle_decision
                            .retry_after_seconds
                        ),
                    },
                )
            ),
        )

    issuance = (
        password_reset_service
        .request_reset(
            email=(
                payload.email
            ),
        )
    )

    if issuance is not None:
        try:
            (
                password_reset_delivery_coordinator
                .deliver(
                    issuance
                )
            )

        except PasswordResetDeliveryError:
            security_event_logger.emit(
                event=(
                    "auth.password_reset.delivery_failed"
                ),
                outcome="failure",
                level=logging.ERROR,
                request=request,
                user_id=(
                    issuance.user_id
                ),
                reason=(
                    "delivery_provider_failure"
                ),
            )

            raise

    security_event_logger.emit(
        event=(
            "auth.password_reset.requested"
        ),
        outcome="success",
        level=logging.INFO,
        request=request,
        account_identifier=(
            payload.email
        ),
    )

    return (
        PasswordResetRequestResponse(
            message=(
                PASSWORD_RESET_REQUEST_ACCEPTED_MESSAGE
            )
        )
    )


# =========================================================
# PASSWORD RESET CONFIRMATION
# =========================================================


@router.post(
    "/password-reset/confirm",
    status_code=(
        status.HTTP_204_NO_CONTENT
    ),
)
def confirm_password_reset(
    request: Request,
    response: Response,
    payload: PasswordResetConfirmRequest,
    password_reset_service: (
        PasswordResetServiceDependency
    ),
) -> None:
    try:
        result = (
            password_reset_service
            .confirm_reset(
                raw_token=(
                    payload
                    .token
                    .get_secret_value()
                ),
                new_password=(
                    payload
                    .new_password
                    .get_secret_value()
                ),
            )
        )

    except (
        InvalidPasswordResetCredentialError
    ) as exc:
        security_event_logger.emit(
            event=(
                "auth.password_reset.failed"
            ),
            outcome="failure",
            level=logging.WARNING,
            request=request,
            reason=(
                "invalid_or_expired_reset_credential"
            ),
        )

        raise HTTPException(
            status_code=(
                status
                .HTTP_400_BAD_REQUEST
            ),
            detail=(
                PASSWORD_RESET_CREDENTIAL_INVALID_MESSAGE
            ),
            headers=(
                auth_error_headers(
                    AuthErrorCode
                    .PASSWORD_RESET_CREDENTIAL_INVALID
                )
            ),
        ) from exc

    except (
        PasswordResetPasswordError
    ) as exc:
        security_event_logger.emit(
            event=(
                "auth.password_reset.failed"
            ),
            outcome="failure",
            level=logging.WARNING,
            request=request,
            reason=(
                "replacement_password_rejected"
            ),
        )

        raise HTTPException(
            status_code=(
                status
                .HTTP_400_BAD_REQUEST
            ),
            detail=(
                PASSWORD_RESET_PASSWORD_REJECTED_MESSAGE
            ),
            headers=(
                auth_error_headers(
                    AuthErrorCode
                    .PASSWORD_RESET_PASSWORD_REJECTED
                )
            ),
        ) from exc

    clear_auth_cookies(
        response
    )

    security_event_logger.emit(
        event=(
            "auth.password_reset.completed"
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
    response_model=(
        TokenResponse
    ),
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

        raise (
            _refresh_credentials_exception()
        )

    csrf_cookie = (
        get_csrf_cookie(
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

        raise (
            _csrf_exception()
        ) from exc

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
                        REFRESH_CREDENTIALS_INVALID_MESSAGE
                    )
                },
                headers=(
                    auth_error_headers(
                        AuthErrorCode
                        .REFRESH_CREDENTIALS_INVALID,
                        additional_headers={
                            "WWW-Authenticate": (
                                "Bearer"
                            ),
                        },
                    )
                ),
            )
        )

        clear_auth_cookies(
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

        raise (
            _refresh_credentials_exception()
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
        clear_auth_cookies(
            response
        )

        return

    csrf_cookie = (
        get_csrf_cookie(
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

        raise (
            _csrf_exception()
        ) from exc

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

        clear_auth_cookies(
            response
        )

        return

    except AuthenticationError:
        clear_auth_cookies(
            response
        )

        return

    clear_auth_cookies(
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

    clear_auth_cookies(
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
    response_model=(
        UserRead
    ),
    status_code=(
        status.HTTP_200_OK
    ),
)
def read_current_user(
    current_user: CurrentUser,
) -> UserRead:
    return (
        UserRead.model_validate(
            current_user
        )
    )