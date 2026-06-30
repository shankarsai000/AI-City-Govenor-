from typing import Any
import uuid
from fastapi import APIRouter, Depends, Query, HTTPException

from app.city_state.domains import CityState, CityStateSyncStatus, DOMAIN_STATE_TYPES
from app.city_state.state_manager import CityStateManager
from app.city_state.resource_lock import ResourceLock
from app.models.city_state_snapshot import CityStateSnapshot
from app.security.dependencies import require_roles
from app.security.principals import AuthenticatedPrincipal

router = APIRouter()


@router.get("/state", response_model=CityState)
async def get_composite_state() -> CityState:
    """Retrieve the full composite city state (Traffic, Power, Water, Emergency)."""
    return await CityStateManager.get_full_state()


@router.get("/sync", response_model=CityStateSyncStatus)
async def get_sync_status() -> CityStateSyncStatus:
    """Retrieve synchronization metadata for the city-state engine."""
    return await CityStateManager.get_sync_status()


@router.get("/state/{domain}")
async def get_domain_state(domain: str) -> Any:
    """Retrieve the physical state of a specific domain."""
    if domain not in DOMAIN_STATE_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
    return await CityStateManager.get_domain_state(domain)


@router.get("/state/{domain}/history")
async def get_domain_history(
    domain: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Retrieve historical state snapshots for a specific domain (time-travel/audit) from MongoDB."""
    if domain not in DOMAIN_STATE_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")

    snapshots = await CityStateSnapshot.find(
        CityStateSnapshot.domain == domain
    ).sort(-CityStateSnapshot.created_at).skip(offset).limit(limit).to_list()

    items = []
    for s in snapshots:
        items.append({
            "id": str(s.id),
            "domain": s.domain,
            "state_data": s.state_data,
            "version": s.version,
            "triggered_by": s.triggered_by,
            "action_id": str(s.action_id) if s.action_id else None,
            "created_at": s.created_at.isoformat()
        })

    return {
        "domain": domain,
        "limit": limit,
        "offset": offset,
        "count": len(items),
        "results": items
    }


@router.get("/locks")
async def get_active_locks(
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "operator", "auditor")),
) -> dict[str, Any]:
    """Get all active distributed resource locks."""
    locks = await ResourceLock.get_all_locks()
    return {"requested_by": principal.username, "locks": locks}


@router.post("/locks/{resource_id}/release")
async def force_release_lock(
    resource_id: str,
    principal: AuthenticatedPrincipal = Depends(require_roles("admin")),
) -> dict[str, Any]:
    """Force release a distributed resource lock (Admin/Operator Console override)."""
    released = await ResourceLock.force_release(resource_id)
    return {
        "resource_id": resource_id,
        "released_by": principal.username,
        "released": released,
        "message": "Resource lock force-released successfully." if released else "No active lock found for resource."
    }
