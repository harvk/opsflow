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
from app.middleware.request_correlation import (
    RequestCorrelationMiddleware,
)
from app.middleware.request_logging import (
    RequestLoggingMiddleware,
)
from app.middleware.security_headers import (
    SecurityHeadersMiddleware,
)


def _count_registered_middleware(
    application: FastAPI,
    middleware_type: object,
) -> int:
    """
    Count exact middleware registrations by class identity.
    """

    return sum(
        1
        for middleware
        in application.user_middleware
        if middleware.cls
        is middleware_type
    )


def test_application_middleware_is_registered_once(
) -> None:
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

    assert (
        _count_registered_middleware(
            application,
            RequestLoggingMiddleware,
        )
        == 1
    )

    assert (
        _count_registered_middleware(
            application,
            RequestCorrelationMiddleware,
        )
        == 1
    )


def test_request_correlation_wraps_request_logging(
) -> None:
    """
    application.user_middleware is stored in runtime order.

    Correlation must execute before logging so the ContextVar
    already contains the current request ID.
    """

    application = (
        create_app()
    )

    registered_middleware = (
        application
        .user_middleware
    )

    assert (
        registered_middleware[0].cls
        is RequestCorrelationMiddleware
    )

    assert (
        registered_middleware[1].cls
        is RequestLoggingMiddleware
    )

    assert (
        registered_middleware[2].cls
        is SecurityHeadersMiddleware
    )

    assert (
        registered_middleware[3].cls
        is CORSMiddleware
    )

    assert (
        registered_middleware[4].cls
        is BrowserTrustBoundaryMiddleware
    )