from __future__ import annotations

from urllib.parse import (
    parse_qsl,
    urlencode,
    urlsplit,
    urlunsplit,
)


class PasswordResetLinkConfigurationError(
    ValueError
):
    """
    Raised when the configured password-reset URL cannot be
    trusted as an absolute HTTP(S) URL.
    """

    pass


class PasswordResetLinkBuilder:
    """
    Builds the browser-facing password-reset URL.

    The raw reset credential belongs only in the URL query
    parameter delivered to the intended account mailbox.

    It must never be logged or persisted as part of this
    operation.
    """

    def __init__(
        self,
        *,
        reset_url: str,
    ) -> None:
        self._reset_url = (
            self._validate_reset_url(
                reset_url
            )
        )

    def build(
        self,
        *,
        raw_token: str,
    ) -> str:
        if not raw_token:
            raise ValueError(
                "raw_token must not be empty."
            )

        parsed = urlsplit(
            self._reset_url
        )

        existing_query = dict(
            parse_qsl(
                parsed.query,
                keep_blank_values=True,
            )
        )

        # Never allow a configured token parameter to survive.
        # The newly issued credential is authoritative.
        existing_query[
            "token"
        ] = raw_token

        query = urlencode(
            existing_query
        )

        return urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                query,
                parsed.fragment,
            )
        )

    @staticmethod
    def _validate_reset_url(
        reset_url: str,
    ) -> str:
        normalized = (
            reset_url.strip()
        )

        if not normalized:
            raise (
                PasswordResetLinkConfigurationError(
                    "Password reset URL "
                    "must not be empty."
                )
            )

        parsed = urlsplit(
            normalized
        )

        if parsed.scheme not in {
            "http",
            "https",
        }:
            raise (
                PasswordResetLinkConfigurationError(
                    "Password reset URL must "
                    "use HTTP or HTTPS."
                )
            )

        if not parsed.netloc:
            raise (
                PasswordResetLinkConfigurationError(
                    "Password reset URL must "
                    "be absolute."
                )
            )

        if parsed.username is not None:
            raise (
                PasswordResetLinkConfigurationError(
                    "Password reset URL must "
                    "not contain user information."
                )
            )

        if parsed.password is not None:
            raise (
                PasswordResetLinkConfigurationError(
                    "Password reset URL must "
                    "not contain user information."
                )
            )

        return normalized