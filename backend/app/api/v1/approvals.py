import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.exceptions import NotFoundError
from app.governance.approval_pipeline import ApprovalPipeline
from app.models.action import Action
from app.models.approval import Approval
from app.security.dependencies import require_roles
from app.security.principals import AuthenticatedPrincipal

router = APIRouter()


class ApprovalDecisionRequest(BaseModel):
    decision: str = Field(..., pattern="^(approved|rejected)$")
    reason: str | None = Field(default=None, max_length=255)


@router.get("/")
async def list_approvals(
    decision: str | None = Query(default=None, pattern="^(pending|approved|rejected)$"),
    limit: int = Query(default=20, ge=1, le=100),
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "operator", "auditor")),
) -> dict[str, object]:
    """List recent escalation approval queue entries."""
    query = {}
    if decision:
        query["decision"] = decision

    # Sort: pending first (approved_at is None), then newest first
    approvals = await Approval.find(query).sort(-Approval.approved_at, -Approval.id).limit(limit).to_list()
    
    results = []
    for approval in approvals:
        action = await Action.get(approval.action_id)
        results.append({
            "approval_id": str(approval.id),
            "action_id": str(approval.action_id),
            "decision": approval.decision,
            "reason": approval.reason,
            "approver_id": str(approval.approver_id) if approval.approver_id else None,
            "approved_at": approval.approved_at.isoformat() if approval.approved_at else None,
            "action_type": action.action_type if action else "unknown",
            "risk_level": action.risk_level if action else "unknown",
            "status": action.status if action else "unknown",
            "requested_at": action.requested_at.isoformat() if action else None,
        })

    return {
        "requested_by": principal.username,
        "count": len(results),
        "results": results,
    }


@router.post("/{approval_id}/decision")
async def submit_decision(
    approval_id: uuid.UUID,
    payload: ApprovalDecisionRequest,
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "operator")),
) -> dict[str, str]:
    """Operator logs an approval decision (approved/rejected) on a pending escalation item."""
    approval = await Approval.get(approval_id)
    if approval is None:
        raise NotFoundError(f"Approval '{approval_id}' was not found.")

    await ApprovalPipeline.submit_decision(
        approval_id=approval_id,
        approver_id=principal.principal_id,
        decision=payload.decision,
        reason=payload.reason,
    )
    return {
        "approval_id": str(approval_id),
        "decision": payload.decision,
        "processed_by": principal.username,
    }
