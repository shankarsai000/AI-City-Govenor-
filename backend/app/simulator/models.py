from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


SimulatorDomain = Literal["traffic", "power", "water", "emergency"]
SimulatorSeverity = Literal["low", "medium", "high", "critical"]


class SyntheticOperationLog(BaseModel):
    """A single synthetic city-operations log record used for analytics and ML."""

    log_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    run_id: uuid.UUID
    operation_id: uuid.UUID
    timestamp: datetime
    domain: SimulatorDomain
    scenario_id: str
    event_type: str
    severity: SimulatorSeverity
    source: str
    actor_id: str
    location: str
    action_type: str | None = None
    status: str
    message: str
    telemetry: dict[str, Any] = Field(default_factory=dict)
    governance: dict[str, Any] = Field(default_factory=dict)
    security: dict[str, Any] = Field(default_factory=dict)
    audit: dict[str, Any] = Field(default_factory=dict)
    labels: list[str] = Field(default_factory=list)
    anomalous: bool = False


class SimulationRunRequest(BaseModel):
    """Operator request for generating a synthetic city dataset."""

    target_log_count: int = Field(default=2_500, ge=100, le=50_000)
    seed: int = Field(default=2026, ge=1, le=2_147_483_647)
    anomaly_rate: float = Field(default=0.03, ge=0.0, le=0.35)
    include_domains: list[SimulatorDomain] = Field(
        default_factory=lambda: ["traffic", "power", "water", "emergency"]
    )
    persist_dataset: bool = True
    publish_summary_event: bool = True


class SimulationDatasetFiles(BaseModel):
    manifest_path: str | None = None
    dataset_path: str | None = None


class SimulationDistributionEntry(BaseModel):
    key: str
    count: int


class SimulationRunManifest(BaseModel):
    """Persistent metadata describing one simulator dataset generation run."""

    run_id: uuid.UUID
    seed: int
    anomaly_rate: float
    requested_log_count: int
    actual_log_count: int
    include_domains: list[SimulatorDomain]
    started_at: datetime
    completed_at: datetime
    files: SimulationDatasetFiles = Field(default_factory=SimulationDatasetFiles)
    domain_distribution: list[SimulationDistributionEntry] = Field(default_factory=list)
    event_distribution: list[SimulationDistributionEntry] = Field(default_factory=list)
    anomaly_distribution: list[SimulationDistributionEntry] = Field(default_factory=list)
    sample_logs: list[SyntheticOperationLog] = Field(default_factory=list)
