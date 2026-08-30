"""Main FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from paymentflow.api import api_router
from paymentflow.config import get_settings
from paymentflow.db.session import close_db, init_db

# Configure logging
settings = get_settings()
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger("paymentflow")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup and shutdown lifespan management."""
    logger.info(f"Starting PaymentFlow Recovery Agent in [{settings.environment}] mode...")
    await init_db()
    yield
    logger.info("Shutting down PaymentFlow Recovery Agent...")
    await close_db()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    application = FastAPI(
        title="PaymentFlow Recovery Agent",
        description="Autonomous Revenue Recovery for Razorpay Failed Payments",
        version="0.1.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(api_router)

    @application.get("/", include_in_schema=False)
    async def root():
        return {
            "name": "PaymentFlow Recovery Agent",
            "version": "0.1.0",
            "status": "online",
            "docs": "/docs",
        }

    return application


app = create_app()
