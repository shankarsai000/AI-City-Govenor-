from typing import Any

from fastapi import APIRouter, Depends, Query

from app.models.action import Action
from app.security.dependencies import require_roles
from app.security.principals import AuthenticatedPrincipal

router = APIRouter()


@router.get("/")
async def list_actions(
    status: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "operator", "auditor")),
) -> dict[str, Any]:
    """List recent governance actions from MongoDB, sorted by request date descending."""
    query = {}
    if status:
        query["status"] = status

    actions = await Action.find(query).sort(-Action.requested_at).limit(limit).to_list()
    return {
        "requested_by": principal.username,
        "count": len(actions),
        "results": [
            {
                "action_id": str(action.id),
                "agent_id": str(action.agent_id),
                "action_type": action.action_type,
                "status": action.status,
                "risk_level": action.risk_level,
                "requires_human": action.requires_human,
                "requested_at": action.requested_at.isoformat(),
                "approved_at": action.approved_at.isoformat() if action.approved_at else None,
                "executed_at": action.executed_at.isoformat() if action.executed_at else None,
            }
            for action in actions
        ],
    }
