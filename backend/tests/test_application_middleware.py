from fastapi import FastAPI
from fastapi.middleware.cors import (
    CORSMiddleware,
)

from app.main import (
    create_app,
)

from app.middleware.broswer_trust import (
    BrowserTrustBoundaryMiddleware,
)

from app.middleware.security_headers import (
    SecurityHeadersMiddleware,
)


def _count_registered_middleware(
    application: FastAPI,
    middleware_type: object,
) -> int:
    """
    Count how many times a particular middleware class is
    registered on the FastAPI application.

    Starlette types Middleware.cls as an internal callable
    middleware-factory protocol rather than as a normal
    type[...].

    Comparing by identity inside the generator avoids the
    overly restrictive list.count() type inference while
    still testing the exact middleware class registered at
    runtime.
    """

    return sum(
        1
        for middleware
        in application.user_middleware
        if middleware.cls
        is middleware_type
    )


def test_security_middleware_is_registered_once() -> None:
    """
    The application factory must produce one authoritative
    middleware stack.

    Duplicate middleware registrations—particularly duplicate
    CORS middleware—can create conflicting browser-security
    behavior.
    """

    application = (
        create_app()
    )

    assert (
        _count_registered_middleware(
            application,
            CORSMiddleware,
        )
        == 1
    )

    assert (
        _count_registered_middleware(
            application,
            BrowserTrustBoundaryMiddleware,
        )
        == 1
    )

    assert (
        _count_registered_middleware(
            application,
            SecurityHeadersMiddleware,
        )
        == 1
    )