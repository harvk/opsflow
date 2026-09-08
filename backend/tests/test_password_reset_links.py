from __future__ import annotations

from urllib.parse import (
    parse_qs,
    urlsplit,
)

import pytest

from app.core.password_reset_links import (
    PasswordResetLinkBuilder,
    PasswordResetLinkConfigurationError,
)


# =========================================================
# BASIC LINK BUILDING
# =========================================================


def test_password_reset_link_contains_token(
) -> None:
    builder = (
        PasswordResetLinkBuilder(
            reset_url=(
                "https://app.example.com/"
                "reset-password"
            )
        )
    )

    reset_url = (
        builder.build(
            raw_token=(
                "opaque-reset-token"
            )
        )
    )

    parsed = urlsplit(
        reset_url
    )

    query = parse_qs(
        parsed.query
    )

    assert (
        parsed.scheme
        == "https"
    )

    assert (
        parsed.netloc
        == "app.example.com"
    )

    assert (
        parsed.path
        == "/reset-password"
    )

    assert query[
        "token"
    ] == [
        "opaque-reset-token"
    ]


# =========================================================
# URL ENCODING
# =========================================================


def test_password_reset_link_url_encodes_token(
) -> None:
    builder = (
        PasswordResetLinkBuilder(
            reset_url=(
                "https://app.example.com/"
                "reset-password"
            )
        )
    )

    raw_token = (
        "abc+/=?&xyz"
    )

    reset_url = (
        builder.build(
            raw_token=raw_token
        )
    )

    query = parse_qs(
        urlsplit(
            reset_url
        ).query
    )

    assert query[
        "token"
    ] == [
        raw_token
    ]


# =========================================================
# EXISTING QUERY PARAMETERS
# =========================================================


def test_password_reset_link_preserves_existing_query_parameters(
) -> None:
    builder = (
        PasswordResetLinkBuilder(
            reset_url=(
                "https://app.example.com/"
                "reset-password"
                "?source=email"
            )
        )
    )

    reset_url = (
        builder.build(
            raw_token=(
                "reset-token"
            )
        )
    )

    query = parse_qs(
        urlsplit(
            reset_url
        ).query
    )

    assert query[
        "source"
    ] == [
        "email"
    ]

    assert query[
        "token"
    ] == [
        "reset-token"
    ]


def test_password_reset_link_replaces_configured_token_parameter(
) -> None:
    builder = (
        PasswordResetLinkBuilder(
            reset_url=(
                "https://app.example.com/"
                "reset-password"
                "?token=unsafe-config-value"
            )
        )
    )

    reset_url = (
        builder.build(
            raw_token=(
                "fresh-token"
            )
        )
    )

    query = parse_qs(
        urlsplit(
            reset_url
        ).query
    )

    assert query[
        "token"
    ] == [
        "fresh-token"
    ]


# =========================================================
# INVALID CONFIGURATION
# =========================================================


@pytest.mark.parametrize(
    "reset_url",
    [
        "",
        "reset-password",
        "/reset-password",
        "javascript:alert(1)",
        "ftp://example.com/reset",
    ],
)
def test_password_reset_link_rejects_invalid_base_url(
    reset_url: str,
) -> None:
    with pytest.raises(
        PasswordResetLinkConfigurationError
    ):
        PasswordResetLinkBuilder(
            reset_url=reset_url
        )


def test_password_reset_link_rejects_embedded_credentials(
) -> None:
    with pytest.raises(
        PasswordResetLinkConfigurationError
    ):
        PasswordResetLinkBuilder(
            reset_url=(
                "https://user:password@"
                "app.example.com/"
                "reset-password"
            )
        )


def test_password_reset_link_rejects_empty_token(
) -> None:
    builder = (
        PasswordResetLinkBuilder(
            reset_url=(
                "https://app.example.com/"
                "reset-password"
            )
        )
    )

    with pytest.raises(
        ValueError
    ):
        builder.build(
            raw_token=""
        )