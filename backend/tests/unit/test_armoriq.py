import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import uuid
from app.armoriq.plan_builder import build_plan, build_prompt
from app.armoriq.intent_service import IntentService, IntentContext
from app.armoriq import is_enabled
from app.armoriq.exceptions import (
    IntentCaptureFailed,
    TokenMintFailed,
    ExecutionBlocked,
    ArmorIQUnavailableError,
)
from app.governance.engine import execute_action_via_armoriq
from app.models.action import Action
from app.models.agent import Agent


def test_plan_builder():
    """Verify that build_plan translates agent types to the correct MCPs and tools."""
    # Traffic agent mapping
    plan_traffic = build_plan("traffic_agent", "adjust_signal_timing", {"intersection": "A"}, "high")
    assert plan_traffic["steps"][0]["mcp"] == "city-traffic-mcp"
    assert plan_traffic["steps"][0]["action"] == "set_signal_phase"
    assert plan_traffic["metadata"]["risk_level"] == "high"

    # Power agent mapping
    plan_power = build_plan("power_agent", "reduce_grid_load", {"zone": 3}, "medium")
    assert plan_power["steps"][0]["mcp"] == "city-power-mcp"
    assert plan_power["steps"][0]["action"] == "adjust_load_balance"

    # Emergency agent mapping
    plan_emergency = build_plan("emergency_agent", "alert_population", {"alert_id": "1"}, "critical")
    assert plan_emergency["steps"][0]["mcp"] == "city-emergency-mcp"
    assert plan_emergency["steps"][0]["action"] == "broadcast_emergency_alert"

    # Prompt builder helper
    prompt = build_prompt("traffic_agent", "adjust_signal_timing", {"zone": "Downtown"})
    assert "Traffic Agent: Adjust Signal Timing in zone Downtown" in prompt


@pytest.mark.asyncio
async def test_intent_service_disabled_mode():
    """Test that when ArmorIQ is not enabled (no client), the service degrades gracefully as no-ops."""
    with patch("app.armoriq.client.is_enabled", return_value=False):
        service = IntentService(user_email="test@test.com")
        
        ctx = await service.prepare_action(
            agent_id=str(uuid.uuid4()),
            agent_type="traffic_agent",
            action_type="reroute_traffic",
            params={"route": "main_st"},
            risk_level="low",
        )
        assert ctx.armoriq_enabled is False
        assert ctx.intent_token_id == "disabled"

        res = await service.execute_action(ctx, {"route": "main_st"})
        assert res["armoriq_enforced"] is False
        assert res["status"] == "executed"


@pytest.mark.asyncio
async def test_intent_service_active_flow():
    """Test full active flow with mocked ArmorIQClient SDK methods."""
    mock_client = MagicMock()
    mock_scoped_client = MagicMock()
    mock_client.for_user.return_value = mock_scoped_client

    # Mock PlanCapture return
    mock_plan_capture = MagicMock()
    mock_plan_capture.id = "plan_123"
    mock_scoped_client.capture_plan.return_value = mock_plan_capture

    # Mock IntentToken return
    mock_intent_token = MagicMock()
    mock_intent_token.id = "tok_456"
    mock_scoped_client.get_intent_token.return_value = mock_intent_token

    # Mock invoke return
    mock_scoped_client.invoke.return_value = {"status": "success", "data": "tool_executed"}

    with patch("app.armoriq.client.is_enabled", return_value=True), \
         patch("app.armoriq.client.get_client", return_value=mock_client):
         
        service = IntentService(user_email="test@test.com")
        
        # Step 1 & 2
        ctx = await service.prepare_action(
            agent_id=str(uuid.uuid4()),
            agent_type="traffic_agent",
            action_type="reroute_traffic",
            params={"route": "main_st"},
            risk_level="medium",
        )
        assert ctx.plan_capture_id == "plan_123"
        assert ctx.intent_token_id == "tok_456"
        assert ctx.armoriq_enabled is True

        # Step 3
        result = await service.execute_action(ctx, {"route": "main_st"})
        assert result["status"] == "success"
        
        # Verify calls
        mock_scoped_client.capture_plan.assert_called_once()
        mock_scoped_client.get_intent_token.assert_called_once()
        mock_scoped_client.invoke.assert_called_once_with(
            mcp="city-traffic-mcp",
            action="update_routing_table",
            intent_token=mock_intent_token,
            params={"route": "main_st"},
            user_email="test@test.com",
        )


@pytest.mark.asyncio
async def test_intent_service_execution_blocked_exception():
    """Verify that proxy blocking exceptions are caught and wrapped in ExecutionBlocked."""
    mock_client = MagicMock()
    mock_scoped_client = MagicMock()
    mock_client.for_user.return_value = mock_scoped_client
    mock_scoped_client.invoke.side_effect = Exception("Blocked by ArmorIQ Policy Proxy")

    with patch("app.armoriq.client.is_enabled", return_value=True), \
         patch("app.armoriq.client.get_client", return_value=mock_client):
         
        service = IntentService()
        ctx = IntentContext(
            plan_capture_id="plan_123",
            intent_token_id="tok_456",
            intent_token=MagicMock(),
            mcp_name="city-traffic-mcp",
            tool_name="update_routing_table",
            armoriq_enabled=True,
        )

        with pytest.raises(ExecutionBlocked):
            await service.execute_action(ctx, {})


@pytest.mark.asyncio
async def test_execute_action_via_armoriq_governance_integration():
    """Test execute_action_via_armoriq utility integrated in the GovernanceEngine."""
    action_id = uuid.uuid4()
    agent_id = uuid.uuid4()

    # Insert Agent and Action documents into the mock MongoDB
    agent_doc = Agent(
        id=agent_id,
        name="traffic_agent",
        domain="traffic",
        capabilities=[],
        public_key="mock_key",
    )
    await agent_doc.insert()

    action_doc = Action(
        id=action_id,
        agent_id=agent_id,
        action_type="reroute_traffic",
        payload={"route": "bypass"},
        status="approved",
        risk_level="medium",
        signature="signature",
        nonce="nonce",
    )
    await action_doc.insert()

    # Mock IntentService methods
    mock_ctx = IntentContext(
        plan_capture_id="pc_111",
        intent_token_id="it_222",
        intent_token=MagicMock(),
        mcp_name="city-traffic-mcp",
        tool_name="update_routing_table",
        armoriq_enabled=True,
    )
    
    with patch("app.armoriq.intent_service.IntentService.prepare_action", return_value=mock_ctx) as mock_prep, \
         patch("app.armoriq.intent_service.IntentService.execute_action", return_value={"status": "executed"}) as mock_exec, \
         patch("app.city_state.state_manager.CityStateManager.apply_mutation", new_callable=AsyncMock), \
         patch("app.governance.engine.AuditLedgerService.append_entry", new_callable=AsyncMock):
         
        await execute_action_via_armoriq(action_id)

        # Verify that ArmorIQ client is invoked
        mock_prep.assert_called_once_with(
            agent_id=str(agent_id),
            agent_type="traffic_agent",
            action_type="reroute_traffic",
            params={"route": "bypass"},
            risk_level="medium",
        )
        mock_exec.assert_called_once_with(intent_ctx=mock_ctx, params={"route": "bypass"})

        # Verify Action status was updated in MongoDB
        updated_action = await Action.get(action_id)
        assert updated_action.status == "executed"
        assert updated_action.plan_id == "it_222"
        assert updated_action.executed_at is not None
