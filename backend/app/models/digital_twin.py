import uuid
from datetime import datetime, timezone
from typing import Any
from beanie import Document
from pydantic import BaseModel, Field

from app.city_state.domains import TrafficState, PowerState, WaterState, EmergencyState


class ResourceUsageState(BaseModel):
    cpu_utilization: float = 0.0
    memory_utilization: float = 0.0
    network_throughput_kbps: float = 0.0
    active_connections: int = 0


class SimulationState(BaseModel):
    scenario_id: str | None = None
    anomaly_rate: float = 0.0
    speed_multiplier: float = 1.0
    running: bool = False


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CityDigitalTwin(Document):
    """
    Living digital twin document representing the entire smart city state,
    resource metrics, simulator variables, sensor readings, and ML overlay.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    traffic: TrafficState = Field(default_factory=TrafficState)
    power: PowerState = Field(default_factory=PowerState)
    water: WaterState = Field(default_factory=WaterState)
    emergency: EmergencyState = Field(default_factory=EmergencyState)
    resource_usage: ResourceUsageState = Field(default_factory=ResourceUsageState)
    current_simulation: SimulationState | None = Field(default_factory=SimulationState)
    sensor_values: dict[str, Any] = Field(default_factory=dict)
    predictions: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=utc_now)
    version: int = 0

    class Settings:
        name = "city_digital_twin"
