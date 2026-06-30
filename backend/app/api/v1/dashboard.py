from typing import Any

from fastapi import APIRouter, Depends, Query

from app.city_state.state_manager import CityStateManager
from app.models.action import Action
from app.models.agent import Agent
from app.models.approval import Approval
from app.security.dependencies import require_roles
from app.security.principals import AuthenticatedPrincipal

router = APIRouter()


@router.get("/summary")
async def get_dashboard_summary(
    action_window: int = Query(default=25, ge=5, le=100),
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "operator", "auditor")),
) -> dict[str, Any]:
    """Retrieve summarized system-wide metrics and alerts for the operator console."""
    city_sync = await CityStateManager.get_sync_status()

    # Aggregate agents by status
    agent_agg = await Agent.get_motor_collection().aggregate([
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]).to_list(length=100)
    agent_rows = [(row["_id"], row["count"]) for row in agent_agg]

    # Aggregate actions by status
    action_agg = await Action.get_motor_collection().aggregate([
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]).to_list(length=100)
    action_rows = [(row["_id"], row["count"]) for row in action_agg]

    # Aggregate actions by risk level
    risk_agg = await Action.get_motor_collection().aggregate([
        {"$group": {"_id": "$risk_level", "count": {"$sum": 1}}}
    ]).to_list(length=100)
    risk_rows = [(row["_id"], row["count"]) for row in risk_agg]

    # Scalar counts
    pending_approvals = await Approval.find(Approval.decision == "pending").count()
    failed_actions = await Action.find(Action.status == "failed").count()

    # Recent actions
    recent_actions = await Action.find_all().sort(-Action.requested_at).limit(action_window).to_list()

    return {
        "requested_by": principal.username,
        "city_sync": city_sync.model_dump(mode="json"),
        "metrics": {
            "agents_total": sum(count for _, count in agent_rows),
            "pending_approvals": pending_approvals,
            "failed_actions": failed_actions,
            "actions_observed": sum(count for _, count in action_rows),
        },
        "agents_by_status": [
            {"status": status, "count": count}
            for status, count in agent_rows
        ],
        "actions_by_status": [
            {"status": status, "count": count}
            for status, count in action_rows
        ],
        "actions_by_risk": [
            {"risk_level": risk_level, "count": count}
            for risk_level, count in risk_rows
        ],
        "alerts": [
            {
                "severity": "critical",
                "title": "Pending approvals require operator action",
                "value": pending_approvals,
            }
            for _ in [0]
            if pending_approvals > 0
        ]
        + [
            {
                "severity": "high",
                "title": "Failed agent actions detected",
                "value": failed_actions,
            }
            for _ in [0]
            if failed_actions > 0
        ],
        "recent_actions": [
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
            for action in recent_actions
        ],
    }
