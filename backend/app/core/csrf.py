from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from app.core.config import settings


CSRF_NONCE_BYTES = 32


def _build_message(session_id: str, nonce: str) -> bytes:
    """
    Build the exact byte sequence that will be authenticated by HMAC.

    Including the length of the session ID makes the encoding
    unambiguous even if formats change in the future.
    """
    return f"{len(session_id)}!{session_id}!{nonce}".encode("utf-8")


def _sign(session_id: str, nonce: str) -> str:
    """
    Produce an HMAC-SHA256 signature tied to both:
      - the authenticated session
      - the random CSRF nonce
    """
    message = _build_message(session_id, nonce)

    digest = hmac.new(
        settings.csrf_secret_key.encode("utf-8"),
        message,
        hashlib.sha256,
    ).digest()

    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def create_csrf_token(session_id: str) -> str:
    """
    Generate a CSRF token bound to one authentication session.

    Token format:

        <random-nonce>.<HMAC-signature>
    """
    nonce = secrets.token_urlsafe(CSRF_NONCE_BYTES)
    signature = _sign(session_id, nonce)

    return f"{nonce}.{signature}"


def verify_csrf_token(
    token: str,
    session_id: str,
) -> bool:
    """
    Verify that a CSRF token was created by this server and
    belongs to the supplied authenticated session.
    """
    try:
        nonce, supplied_signature = token.split(".", maxsplit=1)
    except ValueError:
        return False

    if not nonce or not supplied_signature:
        return False

    expected_signature = _sign(session_id, nonce)

    return hmac.compare_digest(
        supplied_signature,
        expected_signature,
    )


def validate_csrf_pair(
    *,
    cookie_token: str | None,
    header_token: str | None,
    session_id: str,
) -> bool:
    """
    Validate the complete signed double-submit CSRF pattern.

    Requirements:
      1. Cookie token exists.
      2. Header token exists.
      3. Cookie and header contain the same token.
      4. Token's signature is valid for this authentication session.
    """
    if not cookie_token or not header_token:
        return False

    if not hmac.compare_digest(cookie_token, header_token):
        return False

    return verify_csrf_token(
        token=header_token,
        session_id=session_id,
    )