import asyncio
from datetime import datetime, timezone
from typing import Any
import uuid

from app.audit.service import AuditLedgerService
from app.config import get_settings
from app.core.event_bus import publish_event, subscribe_to_events
from app.core.exceptions import CityGovernorError, MLModelNotReadyError
from app.core.logging import get_logger
from app.governance.action_validator import ActionValidator
from app.governance.approval_pipeline import ApprovalPipeline
from app.governance.authorization import check_agent
from app.governance.capability_matrix import validate_capability
from app.governance.policy_engine import PolicyEngine
from app.ml import AnomalyPrediction, get_anomaly_detection_service
from app.models.action import Action
from app.models.agent import Agent
from app.models.policy import Policy
from app.models.decision_graph import (
    DecisionGraph,
    PolicyNode,
    RiskNode,
    ArmorIQNode,
    MLNode,
    HumanApprovalNode,
    ExecutionNode,
)
from app.security.rate_limiter import RateLimiter, build_bucket

logger = get_logger(__name__)

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class GovernanceEngine:
    """
    Main orchestrator of the governance pipeline.
    Subscribes to 'governance.action_requested' events, processes checks,
    and updates action states in MongoDB using Beanie.
    """

    def __init__(self) -> None:
        self._listener_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start listening to incoming governance request events."""
        logger.info("Starting Governance Engine...")
        self._listener_task = asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        try:
            await subscribe_to_events(["governance.action_requested"], self.process_request)
        except asyncio.CancelledError:
            pass

    async def process_request(self, event: dict[str, Any]) -> None:
        """Process a single action request through the governance pipeline."""
        data = event["payload"]
        agent_id = data["agent_id"]
        action_type = data["action_type"]
        payload = data["payload"]
        nonce = data["nonce"]
        signature = data["signature"]
        correlation_id = event.get("correlation_id")

        logger.info(
            "Governance Engine processing request",
            agent_id=agent_id,
            action=action_type,
            correlation_id=correlation_id,
        )

        try:
            # 1. Verify registry status and signature
            action_req_payload = {
                "agent_name": event["source_agent"],
                "action_type": action_type,
                "payload": payload,
                "nonce": nonce,
            }
            agent = await check_agent(agent_id, action_req_payload, signature)

            # 2. Check capabilities
            cap = validate_capability(agent, action_type)
            risk_level = cap.get("risk", "low")
            original_risk_level = risk_level
            base_requires_human = cap.get("requires_human", False)
            requires_human = base_requires_human
            rate_limit = cap.get("rate_limit")

            if rate_limit:
                await RateLimiter.enforce(
                    build_bucket("agent_action", f"{agent_id}:{action_type}"),
                    rate_limit,
                    details={"agent_id": agent_id, "action_type": action_type},
                )

            # 3. Policy Engine Checks (matched policies for decision graph explainability)
            policy_context: dict[str, Any] = {}
            policy_decision = await PolicyEngine.evaluate(
                domain=agent.domain,
                action_type=action_type,
                payload=payload,
                context=policy_context,
            )

            # Trace matching policies for DecisionGraph
            policies_applied = []
            active_policies = await Policy.find(
                Policy.domain == agent.domain, Policy.is_active == True
            ).sort(-Policy.priority).to_list()
            for p in active_policies:
                target_actions = p.conditions.get("actions", [])
                if target_actions and action_type not in target_actions:
                    continue
                if PolicyEngine._match_conditions(p.conditions, payload, policy_context):
                    policies_applied.append(
                        PolicyNode(
                            policy_id=p.id,
                            policy_name=p.name,
                            rule_type=p.rule_type,
                            details=p.conditions,
                        )
                    )

            # 4. State validation Pre-flight check
            city_state_context: dict[str, Any] = {}
            await ActionValidator.pre_flight(action_type, payload, city_state_context)

            # 5. ML anomaly assessment
            runtime_settings = get_settings()
            ml_prediction: AnomalyPrediction | None = None
            ml_escalated = False
            ml_context: dict[str, Any] = {
                "evaluated": False,
                "status": (
                    "disabled"
                    if not runtime_settings.ML_ANOMALY_ESCALATION_ENABLED
                    else "not_ready"
                ),
            }
            ml_node = None
            if runtime_settings.ML_ANOMALY_ESCALATION_ENABLED:
                try:
                    ml_prediction = get_anomaly_detection_service().assess_governance_action(
                        domain=agent.domain,
                        agent_name=agent.name,
                        agent_id=str(agent.id),
                        action_type=action_type,
                        payload=payload,
                        risk_level=risk_level,
                        requires_human=requires_human,
                        policy_decision=policy_decision,
                    )
                    ml_escalated = (
                        ml_prediction.is_anomalous
                        and ml_prediction.confidence >= runtime_settings.ML_ANOMALY_MIN_CONFIDENCE
                    )
                    if ml_escalated:
                        risk_level = _max_risk(risk_level, "high")
                        requires_human = True
                    ml_context = _ml_context_payload(ml_prediction, ml_escalated)
                    
                    ml_node = MLNode(
                        is_anomalous=ml_prediction.is_anomalous,
                        anomaly_score=ml_prediction.anomaly_score,
                        confidence=ml_prediction.confidence,
                        top_features=[f.model_dump() for f in ml_prediction.top_contributing_features]
                    )
                except MLModelNotReadyError:
                    logger.info("ML anomaly model is not ready; governance continues without ML signal")
                except Exception as exc:
                    ml_context = {"evaluated": False, "status": "error", "error": str(exc)}
                    logger.warning(
                        "ML anomaly assessment failed; governance continues without ML signal",
                        action_type=action_type,
                        agent_id=agent_id,
                        error=str(exc),
                    )

            # 6. Insert action registry entry in MongoDB
            action = Action(
                id=uuid.uuid4(),
                agent_id=agent.id,
                action_type=action_type,
                payload=payload,
                status="pending",
                risk_level=risk_level,
                requires_human=requires_human,
                signature=signature,
                nonce=nonce,
            )
            await action.insert()
            action_id = action.id

            audit_entry = await AuditLedgerService.append_entry(
                event_type="governance.action_requested",
                actor_type="agent",
                actor_id=str(agent.id),
                subject_type="action",
                subject_id=str(action_id),
                action_id=action_id,
                correlation_id=correlation_id,
                payload={
                    "agent_name": agent.name,
                    "domain": agent.domain,
                    "action_type": action_type,
                    "original_risk_level": original_risk_level,
                    "risk_level": risk_level,
                    "requires_human": requires_human,
                    "ml_anomaly": ml_context,
                },
            )

            # 7. Evaluate escalation / approval decision
            approval_reasons = _approval_reasons(
                base_requires_human=base_requires_human,
                policy_decision=policy_decision,
                risk_level=risk_level,
                ml_escalated=ml_escalated,
            )
            needs_approval = (
                requires_human or 
                policy_decision == "require_approval" or 
                risk_level in ("high", "critical")
            )
            approval_reason = (
                "; ".join(approval_reasons)
                if approval_reasons
                else "Requires human operator approval"
            )

            # Build initial DecisionGraph
            decision_graph = DecisionGraph(
                id=uuid.uuid4(),
                action_id=action_id,
                agent_id=agent.id,
                agent_name=agent.name,
                domain=agent.domain,
                action_type=action_type,
                policies_applied=policies_applied,
                risk_assessment=RiskNode(
                    risk_level=risk_level,
                    requires_human=requires_human,
                    details={"reasons": approval_reasons}
                ),
                armoriq_decision=ArmorIQNode(
                    status="pending",
                    authorized=False,
                ),
                ml_assessment=ml_node,
                audit_entry_id=audit_entry.id,
            )
            await decision_graph.insert()

            if needs_approval:
                await ApprovalPipeline.escalate(action_id)
                
                # Retrieve approval to link to decision graph
                from app.models.approval import Approval
                app_record = await Approval.find_one(Approval.action_id == action_id)
                if app_record:
                    decision_graph.human_approval = HumanApprovalNode(
                        approval_id=app_record.id,
                        decision="pending",
                        reason=approval_reason
                    )
                    await decision_graph.save()

                await AuditLedgerService.append_entry(
                    event_type="governance.action_pending",
                    actor_type="system",
                    actor_id="governance_engine",
                    subject_type="action",
                    subject_id=str(action_id),
                    action_id=action_id,
                    correlation_id=correlation_id,
                    payload={"reason": approval_reason, "ml_anomaly": ml_context},
                )
                await publish_event(
                    event_type="governance.action_pending",
                    source_agent="governance_engine",
                    payload={"action_id": str(action_id), "reason": approval_reason},
                    correlation_id=correlation_id,
                )
            else:
                # Auto-approve and transition state
                action.status = "approved"
                action.approved_at = datetime.now(timezone.utc)
                await action.save()

                decision_graph.armoriq_decision.status = "approved"
                decision_graph.armoriq_decision.authorized = True
                await decision_graph.save()

                await publish_event(
                    event_type="governance.action_approved",
                    source_agent="governance_engine",
                    payload={"action_id": str(action_id)},
                    correlation_id=correlation_id,
                )
                await AuditLedgerService.append_entry(
                    event_type="governance.action_approved",
                    actor_type="system",
                    actor_id="governance_engine",
                    subject_type="action",
                    subject_id=str(action_id),
                    action_id=action_id,
                    correlation_id=correlation_id,
                    payload={"approval_mode": "automatic"},
                )
                logger.info("Action auto-approved", action_id=action_id)

                # Execute action via ArmorIQ proxy
                await execute_action_via_armoriq(action_id, correlation_id)

        except CityGovernorError as e:
            logger.warning(
                "Governance validation failed",
                agent_id=agent_id,
                action=action_type,
                error_code=e.error_code,
                message=e.message,
            )
            await publish_event(
                event_type="governance.action_denied",
                source_agent="governance_engine",
                payload={"error_code": e.error_code, "message": e.message},
                correlation_id=correlation_id,
            )
            await AuditLedgerService.append_entry(
                event_type="governance.action_denied",
                actor_type="system",
                actor_id="governance_engine",
                subject_type="agent",
                subject_id=agent_id,
                correlation_id=correlation_id,
                payload={"error_code": e.error_code, "message": e.message, "action_type": action_type},
            )
        except Exception as e:
            logger.exception("Unexpected error in governance pipeline", agent_id=agent_id, action=action_type)
            await publish_event(
                event_type="governance.action_failed",
                source_agent="governance_engine",
                payload={"error": str(e)},
                correlation_id=correlation_id,
            )
            await AuditLedgerService.append_entry(
                event_type="governance.action_failed",
                actor_type="system",
                actor_id="governance_engine",
                subject_type="agent",
                subject_id=agent_id,
                correlation_id=correlation_id,
                payload={"error": str(e), "action_type": action_type},
            )
            raise e


def _max_risk(current: str, minimum: str) -> str:
    return current if RISK_ORDER.get(current, 0) >= RISK_ORDER.get(minimum, 0) else minimum


def _ml_context_payload(
    prediction: AnomalyPrediction,
    escalated: bool,
) -> dict[str, Any]:
    return {
        "evaluated": True,
        "status": "scored",
        "model_version": prediction.model_version,
        "label": prediction.label,
        "is_anomalous": prediction.is_anomalous,
        "confidence": prediction.confidence,
        "anomaly_score": prediction.anomaly_score,
        "escalated": escalated,
        "top_contributing_features": [
            entry.model_dump(mode="json")
            for entry in prediction.top_contributing_features
        ],
    }


def _approval_reasons(
    *,
    base_requires_human: bool,
    policy_decision: str,
    risk_level: str,
    ml_escalated: bool,
) -> list[str]:
    reasons: list[str] = []
    if base_requires_human:
        reasons.append("capability requires human approval")
    if policy_decision == "require_approval":
        reasons.append("policy engine requires approval")
    if risk_level in ("high", "critical"):
        reasons.append(f"effective risk level is {risk_level}")
    if ml_escalated:
        reasons.append("ML anomaly detector escalated the action")
    return reasons


async def execute_action_via_armoriq(action_id: uuid.UUID, correlation_id: str | None = None) -> None:
    """
    Executes an approved action through the ArmorIQ intent verification proxy.
    """
    from app.armoriq.intent_service import IntentService

    logger.info("Starting ArmorIQ execution flow", action_id=action_id)

    # 1. Fetch action and agent info from MongoDB using Beanie
    action = await Action.get(action_id)
    if not action:
        logger.error("Action not found for ArmorIQ execution", action_id=action_id)
        return

    agent = await Agent.get(action.agent_id)
    if not agent:
        logger.error("Agent not found for action", action_id=action_id, agent_id=action.agent_id)
        return

    agent_id_str = str(agent.id)
    agent_name = agent.name
    action_type = action.action_type
    payload = action.payload
    risk_level = action.risk_level

    # 2. Call ArmorIQ service
    intent_service = IntentService()
    try:
        # Step 1 & 2: Capture plan and mint intent token
        intent_ctx = await intent_service.prepare_action(
            agent_id=agent_id_str,
            agent_type=agent_name,
            action_type=action_type,
            params=payload,
            risk_level=risk_level,
        )

        # Update DecisionGraph with ArmorIQ information
        dg = await DecisionGraph.find_one(DecisionGraph.action_id == action_id)
        if dg:
            dg.armoriq_decision = ArmorIQNode(
                plan_id=intent_ctx.intent_token_id,
                status="prepared",
                authorized=True,
            )
            await dg.save()

        # Step 3: Invoke the tool via the ArmorIQ proxy
        execution_result = await intent_service.execute_action(
            intent_ctx=intent_ctx,
            params=payload,
        )

        # Apply the state mutation to the digital twin (City State Engine)
        from app.city_state.state_manager import CityStateManager
        await CityStateManager.apply_mutation(
            domain=agent.domain,
            action_type=action_type,
            payload=payload,
            action_id=action_id,
        )

        # Update Action to executed in MongoDB
        action.status = "executed"
        action.plan_id = intent_ctx.intent_token_id
        action.executed_at = datetime.now(timezone.utc)
        await action.save()

        # Finalize DecisionGraph
        if dg:
            dg.execution_result = ExecutionNode(
                status="executed",
                result=execution_result,
                executed_at=datetime.now(timezone.utc)
            )
            await dg.save()

        logger.info(
            "Action executed successfully via ArmorIQ proxy",
            action_id=action_id,
            token_id=intent_ctx.intent_token_id,
        )

        await publish_event(
            event_type="governance.action_executed",
            source_agent="governance_engine",
            payload={"action_id": str(action_id), "result": execution_result},
            correlation_id=correlation_id,
        )
        await AuditLedgerService.append_entry(
            event_type="governance.action_executed",
            actor_type="system",
            actor_id="governance_engine",
            subject_type="action",
            subject_id=str(action_id),
            action_id=action_id,
            correlation_id=correlation_id,
            payload={"plan_id": intent_ctx.intent_token_id, "result": execution_result},
        )

    except Exception as e:
        logger.error(
            "ArmorIQ execution failed",
            action_id=action_id,
            error=str(e),
            exc_info=True,
        )
        action.status = "failed"
        await action.save()

        dg = await DecisionGraph.find_one(DecisionGraph.action_id == action_id)
        if dg:
            dg.execution_result = ExecutionNode(
                status="failed",
                result={"error": str(e)},
                executed_at=datetime.now(timezone.utc)
            )
            await dg.save()

        await publish_event(
            event_type="governance.action_failed",
            source_agent="governance_engine",
            payload={"action_id": str(action_id), "error": str(e)},
            correlation_id=correlation_id,
        )
        await AuditLedgerService.append_entry(
            event_type="governance.action_failed",
            actor_type="system",
            actor_id="governance_engine",
            subject_type="action",
            subject_id=str(action_id),
            action_id=action_id,
            correlation_id=correlation_id,
            payload={"error": str(e)},
        )
