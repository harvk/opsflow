from datetime import (
    datetime,
    timedelta,
    timezone,
)
from uuid import uuid4

import pytest

from app.core.security import (
    TokenValidationError,
    create_access_token,
    create_csrf_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    validate_csrf_token,
)


def test_refresh_token_preserves_session_claims(
) -> None:
    user_id = uuid4()

    session_id = uuid4()

    token_id = uuid4()

    expires_at = (
        datetime.now(
            timezone.utc
        )
        + timedelta(
            days=7
        )
    )

    token = create_refresh_token(
        user_id,
        session_id=session_id,
        token_id=token_id,
        expires_at=expires_at,
    )

    claims = (
        decode_refresh_token(
            token
        )
    )

    assert (
        claims.user_id
        == user_id
    )

    assert (
        claims.session_id
        == session_id
    )

    assert (
        claims.token_id
        == token_id
    )

    assert abs(
        (
            claims.expires_at
            - expires_at
        ).total_seconds()
    ) < 1


def test_refresh_token_cannot_be_used_as_access_token(
) -> None:
    user_id = uuid4()

    token = create_refresh_token(
        user_id,
        session_id=uuid4(),
        token_id=uuid4(),
        expires_at=(
            datetime.now(
                timezone.utc
            )
            + timedelta(
                days=7
            )
        ),
    )

    with pytest.raises(
        TokenValidationError
    ):
        decode_access_token(
            token
        )


def test_access_token_cannot_be_used_as_refresh_token(
) -> None:
    token = (
        create_access_token(
            uuid4()
        )
    )

    with pytest.raises(
        TokenValidationError
    ):
        decode_refresh_token(
            token
        )


def test_csrf_token_is_bound_to_one_session(
) -> None:
    first_session_id = (
        uuid4()
    )

    second_session_id = (
        uuid4()
    )

    csrf_token = (
        create_csrf_token(
            first_session_id
        )
    )

    assert validate_csrf_token(
        first_session_id,
        csrf_token,
    )

    assert not validate_csrf_token(
        second_session_id,
        csrf_token,
    )


def test_tampered_csrf_token_is_rejected(
) -> None:
    session_id = uuid4()

    csrf_token = (
        create_csrf_token(
            session_id
        )
    )

    tampered_token = (
        csrf_token[:-1]
        + (
            "a"
            if csrf_token[-1] != "a"
            else "b"
        )
    )

    assert not validate_csrf_token(
        session_id,
        tampered_token,
    )