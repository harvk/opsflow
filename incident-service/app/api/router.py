from fastapi import APIRouter, Depends

from app.api.dependencies import (
    require_core_backend_token,
)
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
    dependencies=[
        Depends(
            require_core_backend_token
        ),
    ],
)