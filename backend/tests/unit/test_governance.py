import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    CapabilityDeniedError,
    PolicyViolationError,
    ActionValidationError,
)
from app.governance import (
    check_agent,
    validate_capability,
    PolicyEngine,
    ActionValidator,
    ApprovalPipeline,
    verify_signature,
)
from app.governance.engine import GovernanceEngine
from app.models.agent import Agent
from app.models.policy import Policy
from app.models.action import Action


@pytest.mark.asyncio
async def test_authorization_checks():
    """Verify check_agent approves active agents and denies suspended ones."""
    agent_id = uuid.uuid4()

    # Insert agent into mock MongoDB
    agent_model = Agent(
        id=agent_id,
        name="test_traffic",
        domain="traffic",
        status="active",
        public_key="some_key",
        capabilities=[],
    )
    await agent_model.insert()

    # Mock signature verify function to return True
    with patch("app.governance.authorization.verify_signature", return_value=True), \
         patch("app.governance.authorization.NonceStore.register", return_value=True):
        res = await check_agent(str(agent_id), {"nonce": "auth_test_nonce"}, "fake_sig")
        assert res.id == agent_id

    # 2. Test suspended agent raises AuthorizationError
    agent_model.status = "suspended"
    await agent_model.save()

    with patch("app.governance.authorization.verify_signature", return_value=True), \
         patch("app.governance.authorization.NonceStore.register", return_value=True):
        with pytest.raises(AuthorizationError):
            await check_agent(str(agent_id), {"nonce": "auth_test_nonce_2"}, "fake_sig")


def test_verify_signature():
    """Verify verify_signature validation catches invalid signatures."""
    from app.agents import TrafficAgent
    agent = TrafficAgent()
    payload = {"foo": "bar"}
    sig = agent.sign_payload(payload)

    # Validate against actual agent public key
    pubkey = agent.get_public_key_pem()
    assert verify_signature(pubkey, sig, payload) is True

    # Validate with tampered payload
    assert verify_signature(pubkey, sig, {"foo": "tampered"}) is False


def test_capability_matrix():
    """Verify validate_capability confirms declared capabilities."""
    # Create Agent with all required fields for the Beanie Document
    agent = Agent(
        name="power_agent",
        domain="power",
        public_key="mock_key",
        capabilities=[{"action": "load_balance", "risk": "low"}],
    )

    # Valid capability matches
    cap = validate_capability(agent, "load_balance")
    assert cap["risk"] == "low"

    # Invalid capability raises CapabilityDeniedError
    with pytest.raises(CapabilityDeniedError):
        validate_capability(agent, "shed_load")


@pytest.mark.asyncio
async def test_policy_engine_evaluation():
    """Verify PolicyEngine processes deny and allow conditions."""
    # Insert a deny policy into mock MongoDB
    policy_model = Policy(
        name="restrict_shutdown",
        domain="power",
        rule_type="deny",
        conditions={
            "actions": ["emergency_shutdown"],
            "payload": {
                "mw": {"gt": 100}
            }
        },
        priority=100,
        is_active=True,
    )
    await policy_model.insert()

    # Action fails policy: 150mw exceeds 100mw threshold
    with pytest.raises(PolicyViolationError):
        await PolicyEngine.evaluate("power", "emergency_shutdown", {"mw": 150}, {})

    # Action passes policy: 50mw is below threshold
    res = await PolicyEngine.evaluate("power", "emergency_shutdown", {"mw": 50}, {})
    assert res == "allow"


@pytest.mark.asyncio
async def test_action_validator_pre_flight():
    """Verify ActionValidator detects conflicts."""
    # Preflight fails if grid is already in blackout
    with pytest.raises(ActionValidationError):
        await ActionValidator.pre_flight("emergency_shutdown", {}, {"grid_blackout": True})

    # Fails if zone is locked
    with pytest.raises(ActionValidationError):
        await ActionValidator.pre_flight("isolate_zone", {"zone_id": "Zone A"}, {"locked_zones": ["Zone A"]})

    # Passes otherwise
    assert await ActionValidator.pre_flight("isolate_zone", {"zone_id": "Zone B"}, {"locked_zones": ["Zone A"]}) is True


@pytest.mark.asyncio
async def test_approval_pipeline(mock_publish_event):
    """Verify ApprovalPipeline escalates and accepts decisions."""
    action_id = uuid.uuid4()

    # Insert an action first so escalation can find it
    action = Action(
        id=action_id,
        agent_id=uuid.uuid4(),
        action_type="test_action",
        payload={},
        status="pending",
        risk_level="high",
        signature="sig",
        nonce="nonce",
    )
    await action.insert()

    # Trigger escalation — this inserts an Approval record into MongoDB
    with patch("app.governance.approval_pipeline.AuditLedgerService.append_entry", new_callable=AsyncMock):
        await ApprovalPipeline.escalate(action_id)

    # Verify the approval was published
    assert mock_publish_event.called

    # Verify an Approval record was created in MongoDB
    from app.models.approval import Approval
    approval = await Approval.find_one({"action_id": action_id})
    assert approval is not None
    assert approval.decision == "pending"


@pytest.mark.asyncio
async def test_governance_engine_pipeline(mock_publish_event):
    """Verify the complete GovernanceEngine validation pipeline flow."""
    agent_id = uuid.uuid4()

    # Insert agent document so check_agent can find it
    agent_model = Agent(
        id=agent_id,
        name="traffic_agent",
        domain="traffic",
        status="active",
        public_key="some_key",
        capabilities=[{"action": "reroute_traffic", "risk": "medium"}],
    )
    await agent_model.insert()

    engine = GovernanceEngine()
    
    event = {
        "source_agent": "traffic_agent",
        "correlation_id": "corr_abc",
        "payload": {
            "agent_id": str(agent_id),
            "action_type": "reroute_traffic",
            "payload": {"route": "R5"},
            "nonce": "nonce_1",
            "signature": "sig_1"
        }
    }

    # Patch validation dependencies to isolate pipeline orchestration testing.
    # ArmorIQ execution is tested independently in test_armoriq.py.
    from unittest.mock import ANY

    # Create a mock audit entry with a proper UUID id for DecisionGraph validation
    mock_audit_entry = MagicMock()
    mock_audit_entry.id = uuid.uuid4()
    audit_mock = AsyncMock(return_value=mock_audit_entry)

    with patch("app.governance.engine.check_agent", return_value=agent_model) as mock_check, \
         patch("app.governance.engine.validate_capability", return_value={"action": "reroute_traffic", "risk": "medium"}) as mock_cap, \
         patch("app.governance.engine.PolicyEngine.evaluate", return_value="allow") as mock_policy, \
         patch("app.governance.engine.ActionValidator.pre_flight", return_value=True) as mock_val, \
         patch("app.governance.engine.AuditLedgerService.append_entry", new=audit_mock), \
         patch("app.governance.engine.execute_action_via_armoriq", new_callable=AsyncMock) as mock_armoriq_exec:

        await engine.process_request(event)

        assert mock_check.called
        assert mock_cap.called
        assert mock_policy.called
        assert mock_val.called

        # Re-routed request should result in action_approved publication event (risk: medium doesn't require human)
        mock_publish_event.assert_called_with(
            event_type="governance.action_approved",
            source_agent="governance_engine",
            payload={"action_id": ANY},
            correlation_id="corr_abc"
        )

        # ArmorIQ execution should have been triggered for the auto-approved action
        assert mock_armoriq_exec.called
