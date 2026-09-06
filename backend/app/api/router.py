from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.api.routes import (
    auth,
    health,
    incidents,
    services,
)


api_router = APIRouter()


# ---------------------------------------------------------
# Public routes
# ---------------------------------------------------------

api_router.include_router(
    health.router,
    prefix="/health",
    tags=["Health"],
)

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"],
)


# ---------------------------------------------------------
# Authenticated application routes
# ---------------------------------------------------------

api_router.include_router(
    services.router,
    prefix="/services",
    tags=["Services"],
    dependencies=[
        Depends(get_current_user)
    ],
)

api_router.include_router(
    incidents.router,
    prefix="/incidents",
    tags=["Incidents"],
    dependencies=[
        Depends(get_current_user)
    ],
)