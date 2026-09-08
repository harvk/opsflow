from __future__ import annotations

import pytest

from app.core.password_policy import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    PASSWORD_TOO_LONG_MESSAGE,
    PASSWORD_TOO_SHORT_MESSAGE,
    PasswordPolicyViolation,
    validate_new_password,
)


# =========================================================
# POLICY CONSTANTS
# =========================================================


def test_password_policy_uses_expected_length_boundaries(
) -> None:
    """
    Lock the current OpsFlow password-length contract.

    A deliberate future policy change should therefore
    require an explicit test update instead of silently
    changing authentication behavior.
    """

    assert (
        PASSWORD_MIN_LENGTH
        == 15
    )

    assert (
        PASSWORD_MAX_LENGTH
        == 128
    )


# =========================================================
# MINIMUM BOUNDARY
# =========================================================


def test_password_one_character_below_minimum_is_rejected(
) -> None:
    password = (
        "a"
        * (
            PASSWORD_MIN_LENGTH
            - 1
        )
    )

    with pytest.raises(
        PasswordPolicyViolation
    ) as exc_info:
        validate_new_password(
            password
        )

    assert (
        str(
            exc_info.value
        )
        == PASSWORD_TOO_SHORT_MESSAGE
    )


def test_password_at_exact_minimum_is_accepted(
) -> None:
    password = (
        "a"
        * PASSWORD_MIN_LENGTH
    )

    result = (
        validate_new_password(
            password
        )
    )

    assert (
        result
        is None
    )


# =========================================================
# MAXIMUM BOUNDARY
# =========================================================


def test_password_at_exact_maximum_is_accepted(
) -> None:
    password = (
        "a"
        * PASSWORD_MAX_LENGTH
    )

    result = (
        validate_new_password(
            password
        )
    )

    assert (
        result
        is None
    )


def test_password_one_character_above_maximum_is_rejected(
) -> None:
    password = (
        "a"
        * (
            PASSWORD_MAX_LENGTH
            + 1
        )
    )

    with pytest.raises(
        PasswordPolicyViolation
    ) as exc_info:
        validate_new_password(
            password
        )

    assert (
        str(
            exc_info.value
        )
        == PASSWORD_TOO_LONG_MESSAGE
    )


# =========================================================
# UNICODE LENGTH SEMANTICS
# =========================================================


@pytest.mark.parametrize(
    "character",
    [
        "a",
        "密",
        "🙂",
    ],
)
def test_password_policy_accepts_unicode_at_minimum_length(
    character: str,
) -> None:
    """
    Preserve the existing policy's Unicode-code-point length
    semantics rather than introducing an ASCII-only rule.
    """

    password = (
        character
        * PASSWORD_MIN_LENGTH
    )

    assert (
        len(
            password
        )
        == PASSWORD_MIN_LENGTH
    )

    result = (
        validate_new_password(
            password
        )
    )

    assert (
        result
        is None
    )


# =========================================================
# MESSAGE CONTRACT
# =========================================================


def test_minimum_length_message_matches_existing_service_contract(
) -> None:
    assert (
        PASSWORD_TOO_SHORT_MESSAGE
        == (
            "The new password must contain "
            "at least 15 characters."
        )
    )


def test_maximum_length_message_matches_existing_service_contract(
) -> None:
    assert (
        PASSWORD_TOO_LONG_MESSAGE
        == (
            "The new password must not exceed "
            "128 characters."
        )
    )