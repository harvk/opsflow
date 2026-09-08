from __future__ import annotations

import pytest

from app.core.password_policy import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    PASSWORD_TOO_LONG_MESSAGE,
    PASSWORD_TOO_SHORT_MESSAGE,
)

from app.services.authentication_service import (
    AuthenticationService,
    PasswordChangeError,
)

from app.services.password_reset_service import (
    PasswordResetPasswordError,
    PasswordResetService,
)


# =========================================================
# AUTHENTICATION SERVICE TRANSLATION
# =========================================================


def test_authentication_service_translates_short_password_policy_failure(
) -> None:
    """
    AuthenticationService must preserve PasswordChangeError
    even though validation now belongs to the shared core
    policy.
    """

    password = (
        "a"
        * (
            PASSWORD_MIN_LENGTH
            - 1
        )
    )

    with pytest.raises(
        PasswordChangeError
    ) as exc_info:
        AuthenticationService._validate_new_password(
            password
        )

    assert (
        str(
            exc_info.value
        )
        == PASSWORD_TOO_SHORT_MESSAGE
    )


def test_authentication_service_translates_long_password_policy_failure(
) -> None:
    password = (
        "a"
        * (
            PASSWORD_MAX_LENGTH
            + 1
        )
    )

    with pytest.raises(
        PasswordChangeError
    ) as exc_info:
        AuthenticationService._validate_new_password(
            password
        )

    assert (
        str(
            exc_info.value
        )
        == PASSWORD_TOO_LONG_MESSAGE
    )


# =========================================================
# PASSWORD RESET SERVICE TRANSLATION
# =========================================================


def test_password_reset_service_translates_short_password_policy_failure(
) -> None:
    """
    PasswordResetService must preserve its existing
    PasswordResetPasswordError contract.
    """

    password = (
        "a"
        * (
            PASSWORD_MIN_LENGTH
            - 1
        )
    )

    with pytest.raises(
        PasswordResetPasswordError
    ) as exc_info:
        PasswordResetService._validate_new_password(
            password
        )

    assert (
        str(
            exc_info.value
        )
        == PASSWORD_TOO_SHORT_MESSAGE
    )


def test_password_reset_service_translates_long_password_policy_failure(
) -> None:
    password = (
        "a"
        * (
            PASSWORD_MAX_LENGTH
            + 1
        )
    )

    with pytest.raises(
        PasswordResetPasswordError
    ) as exc_info:
        PasswordResetService._validate_new_password(
            password
        )

    assert (
        str(
            exc_info.value
        )
        == PASSWORD_TOO_LONG_MESSAGE
    )


# =========================================================
# VALID BOUNDARIES
# =========================================================


@pytest.mark.parametrize(
    "password",
    [
        "a"
        * PASSWORD_MIN_LENGTH,
        "a"
        * PASSWORD_MAX_LENGTH,
    ],
)
def test_both_services_accept_passwords_allowed_by_shared_policy(
    password: str,
) -> None:
    """
    Both application workflows must accept the exact
    boundaries accepted by the shared password-policy
    component.
    """

    authentication_result = (
        AuthenticationService
        ._validate_new_password(
            password
        )
    )

    reset_result = (
        PasswordResetService
        ._validate_new_password(
            password
        )
    )

    assert (
        authentication_result
        is None
    )

    assert (
        reset_result
        is None
    )