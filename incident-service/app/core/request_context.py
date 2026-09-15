from __future__ import annotations

import re
from contextvars import (
    ContextVar,
    Token,
)
from uuid import uuid4

REQUEST_ID_HEADER = (
    "X-Request-ID"
)

_REQUEST_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9]"
    r"[A-Za-z0-9._:-]{0,127}$"
)

_request_id_context: ContextVar[
    str | None
] = ContextVar(
    "opsflow_request_id",
    default=None,
)


def resolve_request_id(
    supplied_request_id: str | None,
) -> str:
    """
    Return a safe request identifier.

    A caller-provided identifier is accepted only when it is
    a single ASCII token between 1 and 128 characters.

    Invalid, empty, oversized, or missing identifiers are
    replaced with a generated UUIDv4.
    """

    if (
        supplied_request_id is not None
        and _REQUEST_ID_PATTERN.fullmatch(
            supplied_request_id
        )
        is not None
    ):
        return supplied_request_id

    return str(
        uuid4()
    )


def bind_request_id(
    request_id: str,
) -> Token[str | None]:
    """
    Bind a request identifier to the current execution
    context.

    The returned token must be passed to reset_request_id()
    when request processing finishes.
    """

    return _request_id_context.set(
        request_id
    )


def get_request_id(
) -> str | None:
    """
    Return the request identifier bound to the current
    execution context.
    """

    return _request_id_context.get()


def reset_request_id(
    token: Token[str | None],
) -> None:
    """
    Restore the execution context that existed before the
    request identifier was bound.
    """

    _request_id_context.reset(
        token
    )