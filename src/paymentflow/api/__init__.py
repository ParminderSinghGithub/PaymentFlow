"""API router module."""

from fastapi import APIRouter

from paymentflow.api.health import router as health_router
from paymentflow.api.webhooks import router as webhooks_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["Health"])
api_router.include_router(webhooks_router, tags=["Webhooks"])

__all__ = ["api_router"]
