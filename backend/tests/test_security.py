from datetime import timedelta
from uuid import uuid4

import pytest

from app.core.security import (
    TokenValidationError,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
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

    header_segment, payload_segment, signature_segment = (
        token.split(".")
    )

    tampered_signature = (
        (
            "a"
            if signature_segment[0] != "a"
            else "b"
        )
        + signature_segment[1:]
    )

    tampered_token = ".".join(
        [
            header_segment,
            payload_segment,
            tampered_signature,
        ]
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
        
        
def test_refresh_token_round_trip() -> None:
    user_id = uuid4()

    token = create_refresh_token(
        user_id
    )

    decoded_user_id = (
        decode_refresh_token(
            token
        )
    )

    assert (
        decoded_user_id
        == user_id
    )


def test_refresh_token_cannot_be_used_as_access_token() -> None:
    user_id = uuid4()

    refresh_token = (
        create_refresh_token(
            user_id
        )
    )

    with pytest.raises(
        TokenValidationError
    ):
        decode_access_token(
            refresh_token
        )


def test_access_token_cannot_be_used_as_refresh_token() -> None:
    user_id = uuid4()

    access_token = (
        create_access_token(
            user_id
        )
    )

    with pytest.raises(
        TokenValidationError
    ):
        decode_refresh_token(
            access_token
        )


def test_expired_refresh_token_is_rejected() -> None:
    user_id = uuid4()

    refresh_token = (
        create_refresh_token(
            user_id,
            expires_delta=timedelta(
                seconds=-1
            ),
        )
    )

    with pytest.raises(
        TokenValidationError
    ):
        decode_refresh_token(
            refresh_token
        )