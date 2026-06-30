import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from app.city_state.domains import (
    CityState,
    TrafficState,
    PowerState,
    WaterState,
    EmergencyState,
    IncidentRecord,
    DispatchedUnit,
    StateMutation,
    Conflict,
    Resolution,
)
from app.city_state.resource_lock import ResourceLock
from app.city_state.conflict_detector import ConflictDetector
from app.city_state.conflict_resolver import ConflictResolver
from app.city_state.state_manager import CityStateManager
from app.city_state.mutations import build_state_mutation
from app.core.exceptions import (
    ActionValidationError,
    ConflictDetectedError,
    ResourceLockError,
)
import app.core.redis_client


# ── In-Memory Redis Mock ──────────────────────────────────────────────────────

class MockRedis:
    """Mock Redis client using a simple dictionary to store key-value pairs."""
    def __init__(self):
        self.store = {}

    async def exists(self, key: str) -> int:
        return 1 if key in self.store else 0

    async def set(self, key: str, value: str, nx: bool = False, ex: int | None = None) -> bool:
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def delete(self, key: str) -> int:
        if key in self.store:
            del self.store[key]
            return 1
        return 0

    async def eval(self, script: str, numkeys: int, *keys_and_args) -> int:
        # Evaluates script to verify lock holder match
        key = keys_and_args[0]
        arg_holder = keys_and_args[1]
        
        current_holder = self.store.get(key)
        if current_holder == arg_holder:
            del self.store[key]
            return 1
        return 0

    async def keys(self, pattern: str) -> list[str]:
        # Lock prefix matching city:lock:*
        prefix = pattern.replace("*", "")
        return [k for k in self.store.keys() if k.startswith(prefix)]

    async def publish(self, channel: str, message: str) -> int:
        return 1

    async def ping(self) -> bool:
        return True


# ── Pytest Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_redis_client():
    mock_redis = MockRedis()
    # Direct variable injection into core module to support all local namespace imports
    original_client = app.core.redis_client._redis_client
    app.core.redis_client._redis_client = mock_redis
    yield mock_redis
    app.core.redis_client._redis_client = original_client


# ── Unit Tests ────────────────────────────────────────────────────────────────

def test_domain_state_defaults():
    """Verify all four domain states initialize with safe normal-ops baseline."""
    traffic = TrafficState()
    assert len(traffic.intersections) == 12
    assert traffic.congestion_level == 0.15
    assert not traffic.active_corridors
    assert traffic.version == 0

    power = PowerState()
    assert power.grid_load_mw == 120.0
    assert power.capacity_mw == 200.0
    assert len(power.substations) == 4

    water = WaterState()
    assert water.pressure_psi == 65.0
    assert not water.active_isolations

    emergency = EmergencyState()
    assert emergency.alert_level == "green"
    assert not emergency.active_incidents


def test_build_state_mutation_infers_resources():
    """Verify mutation descriptors capture domain and affected resources."""
    mutation = build_state_mutation(
        "activate_emergency_corridor",
        {"route_id": "R-77", "intersections": ["INT-001", "INT-002"]},
    )

    assert mutation.domain == "traffic"
    assert "traffic:domain" in mutation.affected_resources
    assert "traffic:corridor:r-77" in mutation.affected_resources
    assert "traffic:intersection:int-001" in mutation.affected_resources


@pytest.mark.asyncio
async def test_resource_lock_flow(mock_redis_client):
    """Test distributed lock acquisition, rejection, release, and force release."""
    resource = "INT-001"
    holder_a = "traffic_agent"
    holder_b = "emergency_agent"

    # Acquire lock A
    acquired = await ResourceLock.acquire(resource, holder_a, ttl_seconds=10)
    assert acquired is True
    
    # Check is_locked
    lock_info = await ResourceLock.is_locked(resource)
    assert lock_info is not None
    assert lock_info["holder"] == holder_a

    # Lock B try to acquire - should be rejected
    acquired_b = await ResourceLock.acquire(resource, holder_b, ttl_seconds=10)
    assert acquired_b is False

    # Lock B release try - should fail because not owner
    released_b = await ResourceLock.release(resource, holder_b)
    assert released_b is False

    # Lock A release - should succeed
    released_a = await ResourceLock.release(resource, holder_a)
    assert released_a is True

    # Check is_locked is None
    assert await ResourceLock.is_locked(resource) is None

    # Force release
    await ResourceLock.acquire(resource, holder_a, ttl_seconds=10)
    force = await ResourceLock.force_release(resource)
    assert force is True
    assert await ResourceLock.is_locked(resource) is None


@pytest.mark.asyncio
async def test_conflict_detector_same_resource():
    """Test same-resource constraint violations (Traffic road block close road)."""
    current_state = CityState()
    current_state.emergency.active_incidents.append(
        IncidentRecord(
            incident_id="INC-123",
            incident_type="fire",
            location="MAIN_ST",
            severity="critical",
            status="active"
        )
    )

    mutation = StateMutation(
        domain="traffic",
        action_type="close_road",
        description="Close main street road",
        payload={"road_id": "MAIN_ST"}
    )

    conflicts = await ConflictDetector.check("traffic", mutation, current_state)
    assert len(conflicts) == 1
    assert conflicts[0].severity == "critical"
    assert "active emergency" in conflicts[0].description


@pytest.mark.asyncio
async def test_conflict_detector_cross_domain():
    """Test cross-domain dependency constraint violations (Water zone pumps with offline substation)."""
    current_state = CityState()
    # Mark power substation WEST offline
    current_state.power.substations["SUB-WEST"].status = "offline"
    current_state.power.blackout_zones.append("west")

    mutation = StateMutation(
        domain="water",
        action_type="adjust_pressure",
        description="Pressure adjustments West zone pumps",
        payload={"zone_id": "west"}
    )

    conflicts = await ConflictDetector.check("water", mutation, current_state)
    assert len(conflicts) == 1
    assert conflicts[0].severity == "high"
    assert "relies on offline power substation" in conflicts[0].description


@pytest.mark.asyncio
async def test_conflict_detector_duplicate_incident():
    """Test duplicate emergency declarations are escalated instead of duplicated."""
    current_state = CityState()
    current_state.emergency.active_incidents.append(
        IncidentRecord(
            incident_id="INC-777",
            incident_type="fire",
            location="Zone A",
            severity="high",
            status="active",
        )
    )

    mutation = StateMutation(
        domain="emergency",
        action_type="declare_emergency",
        description="Duplicate declaration",
        payload={"incident_id": "INC-777", "location": "Zone A"},
    )

    conflicts = await ConflictDetector.check("emergency", mutation, current_state)
    assert len(conflicts) == 1
    assert conflicts[0].severity == "medium"
    assert "already declared" in conflicts[0].description


@pytest.mark.asyncio
async def test_conflict_resolver_actions():
    """Test priority matrix resolution outcomes (proceed, escalate, block)."""
    # 1. Critical conflict -> Block
    conflicts_crit = [Conflict(
        severity="critical",
        description="Critical failure scenario",
        conflicting_domain="traffic",
        resolution_hint="Abort"
    )]
    res = await ConflictResolver.resolve(conflicts_crit, MagicMock())
    assert res.action == "block"

    # 2. High conflict -> Escalate
    conflicts_high = [Conflict(
        severity="high",
        description="High warning safety",
        conflicting_domain="power",
        resolution_hint="Escalate"
    )]
    res = await ConflictResolver.resolve(conflicts_high, MagicMock())
    assert res.action == "escalate"

    # 3. Low conflict -> Proceed
    conflicts_low = [Conflict(
        severity="low",
        description="Minor warning alert",
        conflicting_domain="water",
        resolution_hint="Proceed"
    )]
    res = await ConflictResolver.resolve(conflicts_low, MagicMock())
    assert res.action == "proceed"


@pytest.mark.asyncio
async def test_state_manager_seeding_and_read_write(mock_redis_client):
    """Verify manager initialization, custom state mutation application, and Redis/DB sync."""
    # Initialize state baseline
    await CityStateManager.initialize()
    
    # Confirm baseline elements exist in Redis
    assert await mock_redis_client.exists("city:state:traffic")
    assert await mock_redis_client.exists("city:state:meta")
    
    # Read Domain State
    traffic = await CityStateManager.get_domain_state("traffic")
    assert isinstance(traffic, TrafficState)
    assert traffic.congestion_level == 0.15

    # Run state mutation (mock audit ledger since apply_mutation writes to it)
    with patch("app.audit.service.AuditLedgerService.append_entry", new_callable=AsyncMock):
        updated_traffic = await CityStateManager.apply_mutation(
            domain="traffic",
            action_type="close_road",
            payload={"road_id": "AVENUE_C"}
        )
    
    assert "AVENUE_C" in updated_traffic.closed_roads
    assert updated_traffic.congestion_level == 0.25 # increased by 0.1
    assert updated_traffic.version == 1

    # Verify state reads back correctly
    read_back = await CityStateManager.get_domain_state("traffic")
    assert read_back.version == 1
    assert "AVENUE_C" in read_back.closed_roads

    sync_status = await CityStateManager.get_sync_status()
    assert sync_status.global_version == 1
    assert sync_status.domain_versions["traffic"] == 1


@pytest.mark.asyncio
async def test_state_manager_rejects_locked_resource(mock_redis_client):
    """Verify a mutation fails fast when a resource-specific lock is already held."""
    await CityStateManager.initialize()
    await ResourceLock.acquire("traffic:road:avenue_c", holder="external_operator", ttl_seconds=10)

    with pytest.raises(ResourceLockError):
        with patch("app.audit.service.AuditLedgerService.append_entry", new_callable=AsyncMock):
            await CityStateManager.apply_mutation(
                domain="traffic",
                action_type="close_road",
                payload={"road_id": "AVENUE_C"},
            )
