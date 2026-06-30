import uuid
from datetime import datetime, timezone

from app.audit.service import AuditLedgerService
from app.core.event_bus import publish_event
from app.core.logging import get_logger
from app.models.action import Action
from app.models.approval import Approval
from app.models.decision_graph import DecisionGraph, HumanApprovalNode, ArmorIQNode

logger = get_logger(__name__)


class ApprovalPipeline:
    """
    Manages operator escalation queues for high-risk actions.
    Puts actions on hold until approved by an operator using Beanie and MongoDB.
    """

    @staticmethod
    async def escalate(action_id: uuid.UUID) -> None:
        """Create a pending approval item and notify listening dashboards."""
        # Update action status to pending
        action = await Action.get(action_id)
        if action:
            action.status = "pending"
            await action.save()

        # Insert approval queue item
        approval = Approval(
            action_id=action_id,
            decision="pending",
        )
        await approval.insert()

        logger.info("Action escalated to operator approval queue", action_id=action_id)

        # Broadcast approval creation to WebSocket clients
        await publish_event(
            event_type="approval.created",
            source_agent="governance_engine",
            payload={
                "action_id": str(action_id),
                "approval_id": str(approval.id),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        await AuditLedgerService.append_entry(
            event_type="approval.created",
            actor_type="system",
            actor_id="governance_engine",
            subject_type="approval",
            subject_id=str(approval.id),
            action_id=action_id,
            payload={
                "action_id": str(action_id),
                "approval_id": str(approval.id),
                "decision": "pending",
            },
        )

    @staticmethod
    async def submit_decision(approval_id: uuid.UUID, approver_id: uuid.UUID, decision: str, reason: str | None = None) -> None:
        """Process operator decision ('approved' or 'rejected') and update action state."""
        # Query approval record
        approval = await Approval.get(approval_id)
        if not approval or approval.decision != "pending":
            raise ValueError("Approval record not found or already processed.")

        # Update approval decision
        approval.decision = decision
        approval.approver_id = approver_id
        approval.reason = reason
        approval.approved_at = datetime.now(timezone.utc)
        await approval.save()

        # Update Action status
        new_action_status = "approved" if decision == "approved" else "rejected"
        action = await Action.get(approval.action_id)
        if action:
            action.status = new_action_status
            action.approved_at = datetime.now(timezone.utc)
            await action.save()

        logger.info(
            "Operator decision submitted",
            approval_id=approval_id,
            decision=decision,
            action_id=approval.action_id,
        )

        # Update DecisionGraph with the human approval result
        dg = await DecisionGraph.find_one(DecisionGraph.action_id == approval.action_id)
        if dg:
            dg.human_approval = HumanApprovalNode(
                approval_id=approval.id,
                decision=decision,
                reason=reason,
                approver=str(approver_id),
                decided_at=datetime.now(timezone.utc)
            )
            if decision == "approved":
                dg.armoriq_decision = ArmorIQNode(status="approved", authorized=True)
            else:
                dg.armoriq_decision = ArmorIQNode(status="denied", authorized=False)
            await dg.save()

        # Notify systems of approval status resolution
        await publish_event(
            event_type=f"approval.{decision}",
            source_agent="governance_engine",
            payload={
                "action_id": str(approval.action_id),
                "approval_id": str(approval_id),
                "decision": decision,
                "reason": reason,
            },
        )
        await AuditLedgerService.append_entry(
            event_type=f"approval.{decision}",
            actor_type="operator",
            actor_id=str(approver_id),
            subject_type="approval",
            subject_id=str(approval_id),
            action_id=approval.action_id,
            payload={
                "action_id": str(approval.action_id),
                "decision": decision,
                "reason": reason,
            },
        )

        # Trigger ArmorIQ execution if approved
        if decision == "approved":
            import asyncio
            from app.governance.engine import execute_action_via_armoriq
            asyncio.create_task(execute_action_via_armoriq(approval.action_id))
