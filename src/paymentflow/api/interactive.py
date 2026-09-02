"""FastAPI REST router for the live interactive recovery demonstration."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from paymentflow.services.interactive_service import (
    DEFAULT_AMOUNT_PAISE,
    InteractiveRecoveryService,
)

router = APIRouter(prefix="/cases/interactive", tags=["Interactive Demo"])


class LaunchScenarioRequest(BaseModel):
    """Payload to launch interactive recovery scenario."""

    scenario_id: str = Field(
        default="CS01",
        description="Canonical scenario identifier (e.g. CS01)",
    )
    amount_paise: int = Field(
        default=DEFAULT_AMOUNT_PAISE,
        description="Transaction amount in paise (default: 250000 = ₹2,500.00)",
    )
    customer_email: str = Field(
        default="demo.buyer@example.com",
        description="Customer email address",
    )
    customer_contact: str = Field(
        default="+919876543210",
        description="Customer contact number",
    )
    reset_previous: bool = Field(
        default=True,
        description="Clean up previous interactive run before launch",
    )


def get_interactive_service() -> InteractiveRecoveryService:
    """Dependency provider for InteractiveRecoveryService."""
    return InteractiveRecoveryService()


@router.post(
    "/launch",
    summary="Launch Interactive Recovery Demonstration Scenario",
    status_code=status.HTTP_200_OK,
)
async def launch_interactive_scenario(
    payload: LaunchScenarioRequest = LaunchScenarioRequest(),
    service: InteractiveRecoveryService = Depends(get_interactive_service),
) -> dict[str, Any]:
    """Initialize interactive CS01 case and run recovery pipeline to Payment Link creation."""
    try:
        result = await service.launch_scenario(
            scenario_id=payload.scenario_id,
            amount_paise=payload.amount_paise,
            customer_email=payload.customer_email,
            customer_contact=payload.customer_contact,
            reset_previous=payload.reset_previous,
        )
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to launch interactive scenario: {exc}",
        ) from exc


@router.get(
    "/status",
    summary="Get Interactive Recovery Case Status and Audit Trail",
    status_code=status.HTTP_200_OK,
)
async def get_interactive_status(
    service: InteractiveRecoveryService = Depends(get_interactive_service),
) -> dict[str, Any]:
    """Query persisted state, payment link status, and full audit trail of the interactive case."""
    return await service.get_status()


@router.post(
    "/verify",
    summary="Authoritatively Verify Interactive Payment Recovery",
    status_code=status.HTTP_200_OK,
)
async def verify_interactive_payment(
    service: InteractiveRecoveryService = Depends(get_interactive_service),
) -> dict[str, Any]:
    """Directly verify Payment Link status against Razorpay API and attribute recovered revenue."""
    return await service.verify_payment()


@router.post(
    "/reset",
    summary="Reset Interactive Demonstration Case",
    status_code=status.HTTP_200_OK,
)
async def reset_interactive_case(
    service: InteractiveRecoveryService = Depends(get_interactive_service),
) -> dict[str, Any]:
    """Safely delete only the interactive demonstration case and its audit events."""
    return await service.reset()
