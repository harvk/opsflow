from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.middleware.security_headers import (
    SecurityHeadersMiddleware,
)

from app.api.router import api_router
from app.core.config import settings

from app.middleware.broswer_trust import BrowserTrustBoundaryMiddleware


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Backend API for the OpsFlow operations management platform.",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(
        api_router,
        prefix=settings.api_v1_prefix,
    )

    return application


app = create_app()


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_origin,
    ],
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-CSRF-Token"
    ],
)


app.add_middleware(
    SecurityHeadersMiddleware,
)

app.add_middleware(
    BrowserTrustBoundaryMiddleware,
    allowed_origins=settings.frontend_origin,
)
