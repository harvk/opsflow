from datetime import timedelta
from uuid import uuid4

import pytest

from app.core.security import (
    TokenValidationError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_does_not_store_plaintext() -> None:
    password = "VerySecurePassword123!"

    hashed = hash_password(password)

    assert hashed != password


def test_verify_password_accepts_correct_password() -> None:
    password = "VerySecurePassword123!"

    hashed = hash_password(password)

    assert verify_password(
        password,
        hashed,
    ) is True


def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password(
        "VerySecurePassword123!"
    )

    assert (
        verify_password(
            "DefinitelyWrongPassword!",
            hashed,
        )
        is False
    )


def test_same_password_produces_different_hashes() -> None:
    password = "VerySecurePassword123!"

    first_hash = hash_password(
        password
    )

    second_hash = hash_password(
        password
    )

    assert first_hash != second_hash

    assert verify_password(
        password,
        first_hash,
    )

    assert verify_password(
        password,
        second_hash,
    )


def test_access_token_round_trip() -> None:
    user_id = uuid4()

    token = create_access_token(
        user_id
    )

    decoded_user_id = (
        decode_access_token(
            token
        )
    )

    assert decoded_user_id == user_id


def test_expired_access_token_is_rejected() -> None:
    user_id = uuid4()

    token = create_access_token(
        user_id,
        expires_delta=timedelta(
            seconds=-1
        ),
    )

    with pytest.raises(
        TokenValidationError
    ):
        decode_access_token(
            token
        )


def test_tampered_access_token_is_rejected() -> None:
    user_id = uuid4()

    token = create_access_token(
        user_id
    )

    tampered_token = (
        token[:-1]
        + (
            "a"
            if token[-1] != "a"
            else "b"
        )
    )

    with pytest.raises(
        TokenValidationError
    ):
        decode_access_token(
            tampered_token
        )


def test_completely_invalid_token_is_rejected() -> None:
    with pytest.raises(
        TokenValidationError
    ):
        decode_access_token(
            "this-is-not-a-jwt"
        )