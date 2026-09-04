"""API router module."""

from fastapi import APIRouter

from paymentflow.api.cases import router as cases_router
from paymentflow.api.health import router as health_router
from paymentflow.api.interactive import router as interactive_router
from paymentflow.api.merchant import (
    checkout_router as merchant_checkout_router,
)
from paymentflow.api.merchant import (
    router as merchant_router,
)
from paymentflow.api.webhooks import router as webhooks_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["Health"])
api_router.include_router(webhooks_router, tags=["Webhooks"])
api_router.include_router(cases_router, tags=["Recovery Cases"])
api_router.include_router(interactive_router)
api_router.include_router(merchant_router)
api_router.include_router(merchant_checkout_router)

__all__ = ["api_router"]
