from app.core.csrf import (
    create_csrf_token,
    validate_csrf_pair,
    verify_csrf_token,
)


def test_create_csrf_token_generates_valid_token() -> None:
    session_id = "session-123"

    token = create_csrf_token(session_id)

    assert token
    assert "." in token
    assert verify_csrf_token(token, session_id) is True


def test_csrf_token_is_bound_to_session() -> None:
    token = create_csrf_token("session-a")

    assert verify_csrf_token(
        token,
        "session-b",
    ) is False


def test_tampered_csrf_token_is_rejected() -> None:
    session_id = "session-123"

    token = create_csrf_token(session_id)

    nonce, signature = token.split(".", maxsplit=1)

    tampered_token = f"{nonce}.{signature}tampered"

    assert verify_csrf_token(
        tampered_token,
        session_id,
    ) is False


def test_csrf_pair_requires_matching_cookie_and_header() -> None:
    session_id = "session-123"

    cookie_token = create_csrf_token(session_id)
    header_token = create_csrf_token(session_id)

    assert validate_csrf_pair(
        cookie_token=cookie_token,
        header_token=header_token,
        session_id=session_id,
    ) is False


def test_valid_csrf_cookie_header_pair_is_accepted() -> None:
    session_id = "session-123"

    token = create_csrf_token(session_id)

    assert validate_csrf_pair(
        cookie_token=token,
        header_token=token,
        session_id=session_id,
    ) is True


def test_missing_csrf_cookie_is_rejected() -> None:
    session_id = "session-123"

    token = create_csrf_token(session_id)

    assert validate_csrf_pair(
        cookie_token=None,
        header_token=token,
        session_id=session_id,
    ) is False


def test_missing_csrf_header_is_rejected() -> None:
    session_id = "session-123"

    token = create_csrf_token(session_id)

    assert validate_csrf_pair(
        cookie_token=token,
        header_token=None,
        session_id=session_id,
    ) is False