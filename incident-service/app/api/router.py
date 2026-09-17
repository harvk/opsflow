from fastapi import APIRouter

from app.api.routes import (
    health,
    incidents,
)

api_router = APIRouter()


# =========================================================
# PUBLIC HEALTH CONTRACT
# =========================================================

api_router.include_router(
    health.router,
    prefix="/health",
    tags=[
        "Health",
    ],
)


# =========================================================
# AUTHENTICATED INCIDENT CONTRACT
# =========================================================

api_router.include_router(
    incidents.router,
    prefix="/incidents",
    tags=[
        "Incidents",
    ],
)