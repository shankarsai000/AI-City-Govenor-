import uuid
from typing import Any
from fastapi import APIRouter, Depends, Query, HTTPException

from app.models.decision_graph import DecisionGraph
from app.security.dependencies import require_roles
from app.security.principals import AuthenticatedPrincipal

router = APIRouter()


@router.get("/")
async def list_decision_graphs(
    limit: int = Query(default=20, ge=1, le=100),
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "operator", "auditor")),
) -> dict[str, Any]:
    """Retrieve a list of recent explainable governance decision graphs."""
    graphs = await DecisionGraph.find_all().sort(-DecisionGraph.created_at).limit(limit).to_list()
    return {
        "requested_by": principal.username,
        "count": len(graphs),
        "results": [g.model_dump(mode="json") for g in graphs],
    }


@router.get("/{action_id}")
async def get_decision_graph(
    action_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "operator", "auditor")),
) -> DecisionGraph:
    """Retrieve the complete explainable governance decision trace for a specific action."""
    graph = await DecisionGraph.find_one(DecisionGraph.action_id == action_id)
    if not graph:
        raise HTTPException(
            status_code=404,
            detail=f"Decision graph trace not found for action '{action_id}'"
        )
    return graph
