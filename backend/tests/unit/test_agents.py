import pytest
from unittest.mock import MagicMock, patch

from app.agents import EmergencyAgent, PowerAgent, TrafficAgent, WaterAgent
from app.models.agent import Agent


@pytest.mark.asyncio
async def test_agent_registration_and_keys(mock_db_session):
    """Verify that an agent generates keys and registers in the DB."""
    agent = TrafficAgent()
    assert agent.status == "idle"
    assert agent._private_key is not None
    assert agent.get_public_key_pem().startswith("-----BEGIN PUBLIC KEY-----")

    # Perform registration
    db_id = await agent.register()
    assert db_id is not None
    assert agent.status == "active"

    # Query MongoDB directly to verify registration
    db_agent = await Agent.get(db_id)
    assert db_agent is not None
    assert db_agent.name == agent.name
    assert db_agent.status == "active"


@pytest.mark.asyncio
async def test_signing_payloads():
    """Verify that agents can cryptographically sign payloads."""
    import json
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    agent = PowerAgent()
    payload = {"control": "shed", "mw": 50}
    signature = agent.sign_payload(payload)
    assert isinstance(signature, str)
    assert len(signature) > 0

    # Cryptographically verify the signature using the public key
    serialized = json.dumps(payload, sort_keys=True).encode("utf-8")
    
    # This should not raise an exception
    agent._public_key.verify(
        bytes.fromhex(signature),
        serialized,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH,
        ),
        hashes.SHA256(),
    )


def test_agent_capabilities():
    """Verify agent capability matrix matches architectural specifications."""
    traffic = TrafficAgent()
    power = PowerAgent()
    water = WaterAgent()
    emergency = EmergencyAgent()

    # Traffic
    traffic_actions = [c["action"] for c in traffic.get_capabilities()]
    assert "reroute_traffic" in traffic_actions
    assert "close_road" in traffic_actions
    assert "activate_emergency_corridor" in traffic_actions

    # Power
    power_actions = [c["action"] for c in power.get_capabilities()]
    assert "load_balance" in power_actions
    assert "shed_load" in power_actions

    # Water
    water_actions = [c["action"] for c in water.get_capabilities()]
    assert "isolate_zone" in water_actions

    # Emergency
    emergency_actions = [c["action"] for c in emergency.get_capabilities()]
    assert "dispatch_unit" in emergency_actions


@pytest.mark.asyncio
async def test_traffic_agent_emergency_response(mock_db_session, mock_publish_event):
    """Verify TrafficAgent requests emergency corridor when incident is declared."""
    traffic = TrafficAgent()
    await traffic.register()

    # Trigger emergency event handler
    emergency_event = {
        "event_id": "test_id",
        "correlation_id": "trace_123",
        "payload": {
            "route_id": "main_street_corridor"
        }
    }
    await traffic._handle_emergency(emergency_event)

    # Check that TrafficAgent published a request to activate emergency corridor
    mock_publish_event.assert_called_once()
    called_args = mock_publish_event.call_args[1]
    assert called_args["event_type"] == "governance.action_requested"
    assert called_args["source_agent"] == "traffic_agent"
    assert called_args["payload"]["action_type"] == "activate_emergency_corridor"
    assert called_args["payload"]["payload"]["route_id"] == "main_street_corridor"
    assert called_args["correlation_id"] == "trace_123"


@pytest.mark.asyncio
async def test_power_agent_overload_response_critical(mock_db_session, mock_publish_event):
    """Verify PowerAgent requests load shedding under critical overload."""
    power = PowerAgent()
    await power.register()

    overload_event = {
        "payload": {
            "severity": "critical",
            "zone": "Zone A"
        }
    }
    await power._handle_overload(overload_event)

    mock_publish_event.assert_called_once()
    called_args = mock_publish_event.call_args[1]
    assert called_args["payload"]["action_type"] == "shed_load"
    assert called_args["payload"]["payload"]["zone"] == "Zone A"


@pytest.mark.asyncio
async def test_power_agent_overload_response_medium(mock_db_session, mock_publish_event):
    """Verify PowerAgent requests load balancing under non-critical overload."""
    power = PowerAgent()
    await power.register()

    overload_event = {
        "payload": {
            "severity": "medium"
        }
    }
    await power._handle_overload(overload_event)

    mock_publish_event.assert_called_once()
    called_args = mock_publish_event.call_args[1]
    assert called_args["payload"]["action_type"] == "load_balance"


@pytest.mark.asyncio
async def test_water_agent_leak_response(mock_db_session, mock_publish_event):
    """Verify WaterAgent isolates zone when leak is detected."""
    water = WaterAgent()
    await water.register()

    leak_event = {
        "payload": {
            "zone_id": "Zone C"
        }
    }
    await water._handle_leak(leak_event)

    mock_publish_event.assert_called_once()
    called_args = mock_publish_event.call_args[1]
    assert called_args["payload"]["action_type"] == "isolate_zone"
    assert called_args["payload"]["payload"]["zone_id"] == "Zone C"


@pytest.mark.asyncio
async def test_emergency_agent_incident_response(mock_db_session, mock_publish_event):
    """Verify EmergencyAgent dispatches units when incidents are reported."""
    emergency = EmergencyAgent()
    await emergency.register()

    report_event = {
        "payload": {
            "incident_type": "fire",
            "location": "Sector 4"
        }
    }
    await emergency._handle_report(report_event)

    mock_publish_event.assert_called_once()
    called_args = mock_publish_event.call_args[1]
    assert called_args["payload"]["action_type"] == "dispatch_unit"
    assert called_args["payload"]["payload"]["type"] == "fire"
    assert called_args["payload"]["payload"]["location"] == "Sector 4"
