from fastapi import APIRouter

from app.api.routes import (
    health,
    incidents,
)

api_router = APIRouter()


api_router.include_router(
    health.router,
    prefix="/health",
    tags=[
        "Health",
    ],
)

api_router.include_router(
    incidents.router,
    prefix="/incidents",
    tags=[
        "Incidents",
    ],
)