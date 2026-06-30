"""Pydantic contracts for Stage 11 anomaly detection."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MLBaseModel(BaseModel):
    model_config = ConfigDict(protected_namespaces=())


class TrainRequest(MLBaseModel):
    """Operator request to train or retrain the anomaly detection model."""

    dataset_run_id: uuid.UUID = Field(
        ...,
        description="Simulator run ID whose persisted JSONL dataset is used.",
    )
    contamination: float = Field(
        default=0.03,
        ge=0.001,
        le=0.35,
        description="Expected anomaly proportion used by Isolation Forest.",
    )
    n_estimators: int = Field(
        default=200,
        ge=50,
        le=1000,
        description="Number of isolation trees.",
    )
    max_samples: int | Literal["auto"] = Field(
        default="auto",
        description="'auto' uses min(256, n_samples), matching scikit-learn.",
    )
    random_state: int = Field(
        default=2026,
        ge=0,
        description="Seed for reproducible model artifacts.",
    )
    train_on_normal_only: bool = Field(
        default=True,
        description="Use simulator anomaly labels to fit on normal records only.",
    )


class FeatureImportanceEntry(MLBaseModel):
    feature_name: str
    importance: float


class TrainingMetrics(MLBaseModel):
    total_samples: int
    normal_samples: int
    anomalous_samples: int
    precision: float
    recall: float
    f1_score: float
    accuracy: float
    true_positive_rate: float
    false_positive_rate: float


class TrainingResult(MLBaseModel):
    model_version: str
    training_dataset_run_id: uuid.UUID
    trained_at: datetime
    metrics: TrainingMetrics
    feature_importances: list[FeatureImportanceEntry]
    hyperparameters: dict[str, Any]
    feature_count: int
    sample_count: int
    artifact_path: str


class PredictRequest(MLBaseModel):
    """Single simulator or governance event to score for anomaly detection."""

    domain: str
    event_type: str = "governance.action_requested"
    action_type: str | None = None
    status: str = "submitted"
    severity: str = "low"
    timestamp: datetime | None = None
    source: str | None = None
    actor_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    telemetry: dict[str, Any] = Field(default_factory=dict)
    governance: dict[str, Any] = Field(default_factory=dict)
    security: dict[str, Any] = Field(default_factory=dict)


class AnomalyPrediction(MLBaseModel):
    label: Literal["normal", "anomalous"]
    anomaly_score: float = Field(
        description="Isolation Forest decision score. Lower values are more anomalous.",
    )
    is_anomalous: bool
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence derived from distance to the learned decision boundary.",
    )
    top_contributing_features: list[FeatureImportanceEntry] = Field(default_factory=list)
    model_version: str


class ModelInfo(MLBaseModel):
    is_ready: bool
    model_version: str | None = None
    trained_at: datetime | None = None
    feature_count: int | None = None
    sample_count: int | None = None
    metrics_summary: TrainingMetrics | None = None
    hyperparameters: dict[str, Any] | None = None


class ModelVersionInfo(MLBaseModel):
    version: str
    trained_at: datetime
    metrics_summary: TrainingMetrics
    is_current: bool


class FeatureSchema(MLBaseModel):
    feature_count: int
    feature_names: list[str]
