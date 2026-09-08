from __future__ import annotations

import pytest

from pydantic import (
    ValidationError,
)

from app.core.password_policy import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
)

from app.schemas.auth import (
    PasswordChangeRequest,
    PasswordResetConfirmRequest,
)


# =========================================================
# TEST VALUES
# =========================================================


REAUTH_TOKEN = (
    "test-reauthentication-token"
)


# Must satisfy the production ResetToken constraint:
#
#     minimum length = 32
#     maximum length = 512
#
# Keeping this token valid ensures password-boundary tests
# fail only because of the password being tested.

VALID_RESET_TOKEN = (
    "test-reset-token-"
    "0123456789abcdef"
    "0123456789abcdef"
)


# =========================================================
# PASSWORD CHANGE HELPER
# =========================================================


def create_password_change_request(
    password: str,
) -> PasswordChangeRequest:
    """
    Validate an external-style password-change payload.

    model_validate() deliberately receives ordinary strings,
    exactly as FastAPI/Pydantic would receive them after
    JSON parsing.

    This avoids passing str directly to the generated model
    constructor, whose static signature expects SecretStr.
    """

    return (
        PasswordChangeRequest
        .model_validate(
            {
                "reauth_token": (
                    REAUTH_TOKEN
                ),
                "new_password": (
                    password
                ),
            }
        )
    )


# =========================================================
# PASSWORD RESET HELPER
# =========================================================


def create_password_reset_request(
    password: str,
) -> PasswordResetConfirmRequest:
    """
    Validate an external-style password-reset payload.

    The reset token is intentionally valid so each password
    test isolates only the new_password field.

    model_validate() is also preferable here because the
    model's static constructor signature correctly describes
    its final field type as SecretStr even though Pydantic
    accepts ordinary strings from JSON.
    """

    return (
        PasswordResetConfirmRequest
        .model_validate(
            {
                "token": (
                    VALID_RESET_TOKEN
                ),
                "new_password": (
                    password
                ),
            }
        )
    )


# =========================================================
# PASSWORD CHANGE — LOWER BOUNDARY
# =========================================================


def test_password_change_schema_rejects_value_below_shared_minimum(
) -> None:
    password = (
        "a"
        * (
            PASSWORD_MIN_LENGTH
            - 1
        )
    )

    with pytest.raises(
        ValidationError
    ) as exc_info:
        create_password_change_request(
            password
        )

    errors = (
        exc_info.value.errors()
    )

    assert any(
        error[
            "loc"
        ]
        == (
            "new_password",
        )
        for error
        in errors
    )


def test_password_change_schema_accepts_shared_minimum(
) -> None:
    password = (
        "a"
        * PASSWORD_MIN_LENGTH
    )

    payload = (
        create_password_change_request(
            password
        )
    )

    assert (
        payload
        .new_password
        .get_secret_value()
        == password
    )


# =========================================================
# PASSWORD CHANGE — UPPER BOUNDARY
# =========================================================


def test_password_change_schema_accepts_shared_maximum(
) -> None:
    password = (
        "a"
        * PASSWORD_MAX_LENGTH
    )

    payload = (
        create_password_change_request(
            password
        )
    )

    assert (
        payload
        .new_password
        .get_secret_value()
        == password
    )


def test_password_change_schema_rejects_value_above_shared_maximum(
) -> None:
    password = (
        "a"
        * (
            PASSWORD_MAX_LENGTH
            + 1
        )
    )

    with pytest.raises(
        ValidationError
    ) as exc_info:
        create_password_change_request(
            password
        )

    errors = (
        exc_info.value.errors()
    )

    assert any(
        error[
            "loc"
        ]
        == (
            "new_password",
        )
        for error
        in errors
    )


# =========================================================
# PASSWORD CHANGE — SECRET HANDLING
# =========================================================


def test_password_change_schema_preserves_secret_string_behavior(
) -> None:
    """
    Shared policy integration must not weaken the schema's
    SecretStr handling.
    """

    password = (
        "a"
        * PASSWORD_MIN_LENGTH
    )

    payload = (
        create_password_change_request(
            password
        )
    )

    representation = (
        repr(
            payload
        )
    )

    assert (
        password
        not in representation
    )

    assert (
        REAUTH_TOKEN
        not in representation
    )

    assert (
        payload
        .new_password
        .get_secret_value()
        == password
    )

    assert (
        payload
        .reauth_token
        .get_secret_value()
        == REAUTH_TOKEN
    )


# =========================================================
# PASSWORD CHANGE — JSON SCHEMA
# =========================================================


def test_password_change_json_schema_uses_shared_policy_boundaries(
) -> None:
    """
    FastAPI/OpenAPI must expose the same password boundaries
    used by the shared backend policy.
    """

    schema = (
        PasswordChangeRequest
        .model_json_schema()
    )

    new_password_schema = (
        schema[
            "properties"
        ][
            "new_password"
        ]
    )

    assert (
        new_password_schema[
            "minLength"
        ]
        == PASSWORD_MIN_LENGTH
    )

    assert (
        new_password_schema[
            "maxLength"
        ]
        == PASSWORD_MAX_LENGTH
    )


# =========================================================
# PASSWORD RESET — LOWER BOUNDARY
# =========================================================


def test_password_reset_schema_rejects_value_below_shared_minimum(
) -> None:
    password = (
        "a"
        * (
            PASSWORD_MIN_LENGTH
            - 1
        )
    )

    with pytest.raises(
        ValidationError
    ) as exc_info:
        create_password_reset_request(
            password
        )

    errors = (
        exc_info.value.errors()
    )

    # The password must be the reason validation failed.

    assert any(
        error[
            "loc"
        ]
        == (
            "new_password",
        )
        for error
        in errors
    )

    # The reset token must remain valid during this test.

    assert not any(
        error[
            "loc"
        ]
        == (
            "token",
        )
        for error
        in errors
    )


def test_password_reset_schema_accepts_shared_minimum(
) -> None:
    password = (
        "a"
        * PASSWORD_MIN_LENGTH
    )

    payload = (
        create_password_reset_request(
            password
        )
    )

    assert (
        payload
        .new_password
        .get_secret_value()
        == password
    )

    assert (
        payload
        .token
        .get_secret_value()
        == VALID_RESET_TOKEN
    )


# =========================================================
# PASSWORD RESET — UPPER BOUNDARY
# =========================================================


def test_password_reset_schema_accepts_shared_maximum(
) -> None:
    password = (
        "b"
        * PASSWORD_MAX_LENGTH
    )

    payload = (
        create_password_reset_request(
            password
        )
    )

    assert (
        payload
        .new_password
        .get_secret_value()
        == password
    )

    assert (
        payload
        .token
        .get_secret_value()
        == VALID_RESET_TOKEN
    )


def test_password_reset_schema_rejects_value_above_shared_maximum(
) -> None:
    password = (
        "a"
        * (
            PASSWORD_MAX_LENGTH
            + 1
        )
    )

    with pytest.raises(
        ValidationError
    ) as exc_info:
        create_password_reset_request(
            password
        )

    errors = (
        exc_info.value.errors()
    )

    assert any(
        error[
            "loc"
        ]
        == (
            "new_password",
        )
        for error
        in errors
    )

    assert not any(
        error[
            "loc"
        ]
        == (
            "token",
        )
        for error
        in errors
    )


# =========================================================
# PASSWORD RESET — SECRET HANDLING
# =========================================================


def test_password_reset_schema_preserves_secret_string_behavior(
) -> None:
    """
    Neither the reset bearer credential nor replacement
    password may appear in ordinary Pydantic repr output.
    """

    password = (
        "a"
        * PASSWORD_MIN_LENGTH
    )

    payload = (
        create_password_reset_request(
            password
        )
    )

    representation = (
        repr(
            payload
        )
    )

    assert (
        password
        not in representation
    )

    assert (
        VALID_RESET_TOKEN
        not in representation
    )

    assert (
        payload
        .new_password
        .get_secret_value()
        == password
    )

    assert (
        payload
        .token
        .get_secret_value()
        == VALID_RESET_TOKEN
    )


# =========================================================
# PASSWORD RESET — JSON SCHEMA
# =========================================================


def test_password_reset_json_schema_uses_shared_policy_boundaries(
) -> None:
    """
    Password-reset confirmation must advertise exactly the
    same replacement-password limits as password change.
    """

    schema = (
        PasswordResetConfirmRequest
        .model_json_schema()
    )

    new_password_schema = (
        schema[
            "properties"
        ][
            "new_password"
        ]
    )

    assert (
        new_password_schema[
            "minLength"
        ]
        == PASSWORD_MIN_LENGTH
    )

    assert (
        new_password_schema[
            "maxLength"
        ]
        == PASSWORD_MAX_LENGTH
    )


# =========================================================
# PASSWORD RESET — RESET TOKEN CONTRACT
# =========================================================


def test_password_reset_schema_rejects_short_reset_token(
) -> None:
    """
    Test reset-token validation independently from password
    validation.

    model_validate() receives ordinary strings just as the
    actual HTTP/JSON boundary does.
    """

    password = (
        "a"
        * PASSWORD_MIN_LENGTH
    )

    with pytest.raises(
        ValidationError
    ) as exc_info:
        (
            PasswordResetConfirmRequest
            .model_validate(
                {
                    "token": (
                        "too-short"
                    ),
                    "new_password": (
                        password
                    ),
                }
            )
        )

    errors = (
        exc_info.value.errors()
    )

    assert any(
        error[
            "loc"
        ]
        == (
            "token",
        )
        for error
        in errors
    )

    assert not any(
        error[
            "loc"
        ]
        == (
            "new_password",
        )
        for error
        in errors
    )