from fastapi import (
    APIRouter,
    Depends,
)

from app.api.dependencies import (
    get_current_user,
)
from app.api.routes import (
    auth,
    health,
    incidents,
    internal_services,
    overview,
    services,
)


api_router = (
    APIRouter()
)


# =========================================================
# PUBLIC ROUTES
# =========================================================

api_router.include_router(
    health.router,
    prefix="/health",
    tags=[
        "Health"
    ],
)

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=[
        "Authentication"
    ],
)


# =========================================================
# INTERNAL SERVICE ROUTES
# =========================================================

api_router.include_router(
    internal_services.router,
    prefix="/internal/services",
    tags=[
        "Internal"
    ],
    include_in_schema=False,
)


# =========================================================
# AUTHENTICATED APPLICATION ROUTES
# =========================================================

api_router.include_router(
    overview.router,
    prefix="/overview",
    tags=[
        "Overview"
    ],
    dependencies=[
        Depends(
            get_current_user
        )
    ],
)

api_router.include_router(
    services.router,
    prefix="/services",
    tags=[
        "Services"
    ],
    dependencies=[
        Depends(
            get_current_user
        )
    ],
)

api_router.include_router(
    incidents.router,
    prefix="/incidents",
    tags=[
        "Incidents"
    ],
    dependencies=[
        Depends(
            get_current_user
        )
    ],
)