from typing import Any
from fastapi import APIRouter, Depends, HTTPException

from app.models.digital_twin import CityDigitalTwin
from app.security.dependencies import require_roles
from app.security.principals import AuthenticatedPrincipal

router = APIRouter()


@router.get("/")
async def get_digital_twin(
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "operator", "auditor")),
) -> CityDigitalTwin:
    """Retrieve the entire living smart city digital twin projection."""
    twin = await CityDigitalTwin.find_all().first_or_none()
    if not twin:
        raise HTTPException(status_code=404, detail="Digital twin state not initialized.")
    return twin


@router.get("/predictions")
async def get_digital_twin_predictions(
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "operator", "auditor")),
) -> dict[str, Any]:
    """Retrieve machine learning overlay predictions from the digital twin projection."""
    twin = await CityDigitalTwin.find_all().first_or_none()
    if not twin:
        raise HTTPException(status_code=404, detail="Digital twin state not initialized.")
    return {
        "predictions": twin.predictions,
        "updated_at": twin.updated_at.isoformat(),
        "version": twin.version,
    }


@router.get("/{domain}")
async def get_domain_twin_state(
    domain: str,
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "operator", "auditor")),
) -> Any:
    """Retrieve the digital twin state of a specific city domain."""
    if domain not in ("traffic", "power", "water", "emergency"):
        raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")

    twin = await CityDigitalTwin.find_all().first_or_none()
    if not twin:
        raise HTTPException(status_code=404, detail="Digital twin state not initialized.")

    return getattr(twin, domain)
