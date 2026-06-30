from typing import Any
import uuid

from fastapi import APIRouter, Depends, Query

from app.security.dependencies import require_roles
from app.security.principals import AuthenticatedPrincipal
from app.simulator import SimulationRunRequest, SyntheticCitySimulator

router = APIRouter()
simulator = SyntheticCitySimulator()


@router.post("/runs")
async def create_simulation_run(
    payload: SimulationRunRequest,
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    manifest = await simulator.run(payload)
    return {
        "requested_by": principal.username,
        "run": manifest.model_dump(mode="json"),
    }


@router.get("/runs")
async def list_simulation_runs(
    limit: int = Query(default=20, ge=1, le=100),
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "operator", "auditor")),
) -> dict[str, Any]:
    runs = simulator.list_runs(limit=limit)
    return {
        "requested_by": principal.username,
        "count": len(runs),
        "results": [run.model_dump(mode="json") for run in runs],
    }


@router.get("/runs/{run_id}")
async def get_simulation_run(
    run_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "operator", "auditor")),
) -> dict[str, Any]:
    manifest = simulator.get_run(run_id)
    return {
        "requested_by": principal.username,
        "run": manifest.model_dump(mode="json"),
    }


@router.get("/runs/{run_id}/dataset")
async def get_simulation_dataset_preview(
    run_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "operator", "auditor")),
) -> dict[str, Any]:
    preview = simulator.read_dataset_preview(run_id, limit=limit, offset=offset)
    return {
        "requested_by": principal.username,
        "run_id": str(run_id),
        "limit": limit,
        "offset": offset,
        "count": len(preview),
        "results": [entry.model_dump(mode="json") for entry in preview],
    }
