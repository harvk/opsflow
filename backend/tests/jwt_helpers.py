from __future__ import annotations

import base64
import binascii


def tamper_jwt_payload(
    token: str,
) -> str:
    """
    Return a JWT whose payload bytes have been changed without
    changing the original signature.

    The decoded payload remains valid JSON because only trailing
    JSON whitespace is added. This ensures tests exercise JWT
    signature-integrity validation rather than merely producing a
    malformed token.

    Raises:
        ValueError:
            If the supplied token is not a three-segment JWT.
    """

    parts = token.split(".")

    if len(parts) != 3:
        raise ValueError(
            "JWT must contain exactly three segments."
        )

    (
        header_segment,
        payload_segment,
        signature_segment,
    ) = parts

    padding = (
        "="
        * (
            -len(payload_segment)
            % 4
        )
    )

    try:
        payload_bytes = (
            base64.urlsafe_b64decode(
                payload_segment
                + padding
            )
        )
    except (
        ValueError,
        binascii.Error,
    ) as exc:
        raise ValueError(
            "JWT payload is not valid Base64URL data."
        ) from exc

    # JSON permits trailing whitespace. Adding one byte keeps
    # the payload syntactically valid while guaranteeing that
    # the signed bytes differ from the original payload.
    tampered_payload_bytes = (
        payload_bytes
        + b" "
    )

    tampered_payload_segment = (
        base64.urlsafe_b64encode(
            tampered_payload_bytes
        )
        .rstrip(
            b"="
        )
        .decode(
            "ascii"
        )
    )

    return (
        f"{header_segment}."
        f"{tampered_payload_segment}."
        f"{signature_segment}"
    )
