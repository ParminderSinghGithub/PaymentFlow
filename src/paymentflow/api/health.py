"""Health check endpoint."""

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from paymentflow.config import Settings, get_settings
from paymentflow.db.session import ping_db

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str
    environment: str
    database: str
    version: str = "0.1.0"


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Application Health Check",
)
async def health_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Return health status of the application and database."""
    db_connected = await ping_db()

    return HealthResponse(
        status="ok" if db_connected else "degraded",
        environment=settings.environment,
        database="connected" if db_connected else "disconnected",
        version="0.1.0",
    )

