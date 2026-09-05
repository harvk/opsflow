from fastapi import APIRouter

from app.api.routes import health, services

api_router = APIRouter()

api_router.include_router(
    health.router,
    prefix="/health",
    tags=["Health"],
)

api_router.include_router(
    services.router,
    prefix="/services",
    tags=["Services"],
)
