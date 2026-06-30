from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.preprocessing import StandardScaler

from app.config import get_settings
from app.core.exceptions import MLDatasetError, MLModelNotReadyError, NotFoundError
from app.core.logging import get_logger
from app.ml.features import extract_features, extract_features_batch, get_feature_count, get_feature_names
from app.ml.models import (
    AnomalyPrediction,
    FeatureImportanceEntry,
    ModelInfo,
    ModelVersionInfo,
    PredictRequest,
    TrainRequest,
    TrainingMetrics,
    TrainingResult,
)
from app.simulator.models import SyntheticOperationLog
from app.simulator.service import SyntheticCitySimulator

logger = get_logger(__name__)

ARTIFACT_SCHEMA_VERSION = 1
CURRENT_POINTER_FILE = "current_model.json"


@dataclass
class LoadedAnomalyModel:
    version: str
    trained_at: datetime
    estimator: IsolationForest
    scaler: StandardScaler
    feature_names: list[str]
    metrics: TrainingMetrics
    feature_importances: list[FeatureImportanceEntry]
    hyperparameters: dict[str, Any]
    sample_count: int
    artifact_path: Path


class AnomalyDetectionService:
    """Train, persist, load, and score Isolation Forest anomaly models."""

    def __init__(
        self,
        *,
        artifact_dir: Path | None = None,
        simulator: SyntheticCitySimulator | None = None,
    ) -> None:
        settings = get_settings()
        self.artifact_dir = artifact_dir or settings.ML_MODEL_DIR
        self.simulator = simulator or SyntheticCitySimulator()
        self._loaded_model: LoadedAnomalyModel | None = None

    def train_from_simulation_run(self, request: TrainRequest) -> TrainingResult:
        """Train an Isolation Forest model from a persisted simulator dataset."""

        logs = self._load_dataset(request.dataset_run_id)
        if not logs:
            raise MLDatasetError("Simulation dataset is empty.")

        normal_logs = [log for log in logs if not log.anomalous]
        training_logs = normal_logs if request.train_on_normal_only else logs
        if len(training_logs) < 50:
            raise MLDatasetError(
                "Dataset does not contain enough training records.",
                details={
                    "minimum_required": 50,
                    "available_training_records": len(training_logs),
                    "train_on_normal_only": request.train_on_normal_only,
                },
            )

        training_records = [log.model_dump(mode="json") for log in training_logs]
        evaluation_records = [log.model_dump(mode="json") for log in logs]
        x_train = extract_features_batch(training_records)
        x_eval = extract_features_batch(evaluation_records)

        scaler = StandardScaler()
        x_train_scaled = scaler.fit_transform(x_train)
        x_eval_scaled = scaler.transform(x_eval)

        estimator = IsolationForest(
            contamination=request.contamination,
            n_estimators=request.n_estimators,
            max_samples=request.max_samples,
            random_state=request.random_state,
            n_jobs=-1,
        )
        estimator.fit(x_train_scaled)

        y_true = np.array([1 if log.anomalous else 0 for log in logs], dtype=np.int8)
        y_pred = np.array([1 if prediction == -1 else 0 for prediction in estimator.predict(x_eval_scaled)])
        metrics = self._compute_metrics(y_true, y_pred)
        feature_importances = self._estimate_feature_importances(estimator, x_eval_scaled)

        trained_at = datetime.now(timezone.utc)
        model_version = self._build_model_version(trained_at, request.dataset_run_id)
        hyperparameters = {
            "algorithm": "IsolationForest",
            "contamination": request.contamination,
            "n_estimators": request.n_estimators,
            "max_samples": request.max_samples,
            "random_state": request.random_state,
            "train_on_normal_only": request.train_on_normal_only,
        }

        artifact = {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "model_version": model_version,
            "trained_at": trained_at.isoformat(),
            "training_dataset_run_id": str(request.dataset_run_id),
            "estimator": estimator,
            "scaler": scaler,
            "feature_names": get_feature_names(),
            "feature_count": get_feature_count(),
            "sample_count": len(training_logs),
            "metrics": metrics.model_dump(),
            "feature_importances": [entry.model_dump() for entry in feature_importances],
            "hyperparameters": hyperparameters,
        }
        artifact_path = self._artifact_path(model_version)
        metadata_path = self._metadata_path(model_version)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(artifact, artifact_path)
        metadata_path.write_text(
            json.dumps(self._metadata_from_artifact(artifact, artifact_path), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
        self._write_current_pointer(model_version, artifact_path)
        self._loaded_model = self._loaded_model_from_artifact(artifact, artifact_path)

        logger.info(
            "Isolation Forest model trained",
            model_version=model_version,
            dataset_run_id=str(request.dataset_run_id),
            sample_count=len(training_logs),
            total_samples=len(logs),
        )

        return TrainingResult(
            model_version=model_version,
            training_dataset_run_id=request.dataset_run_id,
            trained_at=trained_at,
            metrics=metrics,
            feature_importances=feature_importances,
            hyperparameters=hyperparameters,
            feature_count=get_feature_count(),
            sample_count=len(training_logs),
            artifact_path=str(artifact_path),
        )

    def predict(self, request: PredictRequest | dict[str, Any]) -> AnomalyPrediction:
        """Score one event using the current trained model."""

        loaded_model = self._ensure_loaded_model()
        record = request.model_dump(mode="json") if isinstance(request, PredictRequest) else request
        feature_vector = extract_features(record)
        if feature_vector.shape[0] != len(loaded_model.feature_names):
            raise MLDatasetError(
                "Feature schema mismatch between request and loaded model.",
                details={
                    "request_feature_count": int(feature_vector.shape[0]),
                    "model_feature_count": len(loaded_model.feature_names),
                },
            )

        scaled_vector = loaded_model.scaler.transform(feature_vector.reshape(1, -1))
        anomaly_score = float(loaded_model.estimator.decision_function(scaled_vector)[0])
        prediction = int(loaded_model.estimator.predict(scaled_vector)[0])
        is_anomalous = prediction == -1
        return AnomalyPrediction(
            label="anomalous" if is_anomalous else "normal",
            anomaly_score=anomaly_score,
            is_anomalous=is_anomalous,
            confidence=self._confidence_from_score(anomaly_score),
            top_contributing_features=self._top_contributing_features(scaled_vector[0], loaded_model),
            model_version=loaded_model.version,
        )

    def assess_governance_action(
        self,
        *,
        domain: str,
        agent_name: str,
        agent_id: str,
        action_type: str,
        payload: dict[str, Any],
        risk_level: str,
        requires_human: bool,
        policy_decision: str,
    ) -> AnomalyPrediction:
        """Build and score the live governance event shape."""

        event = {
            "domain": domain,
            "event_type": "governance.action_requested",
            "action_type": action_type,
            "status": "submitted",
            "severity": risk_level,
            "timestamp": datetime.now(timezone.utc),
            "source": agent_name,
            "actor_id": agent_id,
            "payload": payload,
            "governance": {
                "risk_level": risk_level,
                "requires_human": requires_human,
                "policy_outcome": policy_decision,
            },
            "security": {
                "signature_valid": True,
                "nonce_reuse_detected": False,
                "replay_risk_score": 0.0,
            },
        }
        return self.predict(event)

    def get_model_info(self) -> ModelInfo:
        loaded_model = self._try_load_current_model()
        if loaded_model is None:
            return ModelInfo(is_ready=False)

        return ModelInfo(
            is_ready=True,
            model_version=loaded_model.version,
            trained_at=loaded_model.trained_at,
            feature_count=len(loaded_model.feature_names),
            sample_count=loaded_model.sample_count,
            metrics_summary=loaded_model.metrics,
            hyperparameters=loaded_model.hyperparameters,
        )

    def list_model_versions(self) -> list[ModelVersionInfo]:
        current_version = self._read_current_version()
        versions: list[ModelVersionInfo] = []
        for metadata_path in self.artifact_dir.glob("*.metadata.json"):
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            versions.append(
                ModelVersionInfo(
                    version=metadata["model_version"],
                    trained_at=datetime.fromisoformat(metadata["trained_at"]),
                    metrics_summary=TrainingMetrics.model_validate(metadata["metrics"]),
                    is_current=metadata["model_version"] == current_version,
                )
            )
        return sorted(versions, key=lambda version: version.trained_at, reverse=True)

    def _load_dataset(self, run_id: uuid.UUID) -> list[SyntheticOperationLog]:
        try:
            manifest = self.simulator.get_run(run_id)
        except NotFoundError:
            raise

        if not manifest.files.dataset_path:
            raise MLDatasetError(
                "Simulation run does not have a persisted dataset.",
                details={"run_id": str(run_id)},
            )

        dataset_path = Path(manifest.files.dataset_path)
        if not dataset_path.exists():
            raise MLDatasetError(
                "Simulation dataset file is missing.",
                details={"run_id": str(run_id), "dataset_path": str(dataset_path)},
            )

        logs: list[SyntheticOperationLog] = []
        with dataset_path.open("r", encoding="utf-8") as file_handle:
            for line_number, line in enumerate(file_handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    logs.append(SyntheticOperationLog.model_validate_json(stripped))
                except ValueError as exc:
                    raise MLDatasetError(
                        "Simulation dataset contains an invalid JSONL row.",
                        details={"line_number": line_number, "error": str(exc)},
                    ) from exc
        return logs

    def _ensure_loaded_model(self) -> LoadedAnomalyModel:
        loaded_model = self._try_load_current_model()
        if loaded_model is None:
            raise MLModelNotReadyError(
                "No trained anomaly model is available. Train from a simulator run first."
            )
        return loaded_model

    def _try_load_current_model(self) -> LoadedAnomalyModel | None:
        if self._loaded_model is not None:
            return self._loaded_model

        pointer_path = self.artifact_dir / CURRENT_POINTER_FILE
        if not pointer_path.exists():
            return None
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        artifact_path = Path(pointer["artifact_path"])
        if not artifact_path.exists():
            return None

        artifact = joblib.load(artifact_path)
        self._loaded_model = self._loaded_model_from_artifact(artifact, artifact_path)
        return self._loaded_model

    @staticmethod
    def _compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> TrainingMetrics:
        true_positive = int(((y_true == 1) & (y_pred == 1)).sum())
        false_positive = int(((y_true == 0) & (y_pred == 1)).sum())
        true_negative = int(((y_true == 0) & (y_pred == 0)).sum())
        false_negative = int(((y_true == 1) & (y_pred == 0)).sum())
        positive_total = true_positive + false_negative
        negative_total = true_negative + false_positive

        return TrainingMetrics(
            total_samples=int(y_true.size),
            normal_samples=int((y_true == 0).sum()),
            anomalous_samples=int((y_true == 1).sum()),
            precision=float(precision_score(y_true, y_pred, zero_division=0)),
            recall=float(recall_score(y_true, y_pred, zero_division=0)),
            f1_score=float(f1_score(y_true, y_pred, zero_division=0)),
            accuracy=float(accuracy_score(y_true, y_pred)),
            true_positive_rate=float(true_positive / positive_total) if positive_total else 0.0,
            false_positive_rate=float(false_positive / negative_total) if negative_total else 0.0,
        )

    @staticmethod
    def _estimate_feature_importances(
        estimator: IsolationForest,
        x_eval_scaled: np.ndarray,
    ) -> list[FeatureImportanceEntry]:
        if x_eval_scaled.size == 0:
            return []

        rng = np.random.default_rng(2026)
        reference = x_eval_scaled
        if reference.shape[0] > 1000:
            row_indices = rng.choice(reference.shape[0], size=1000, replace=False)
            reference = reference[row_indices]

        baseline_scores = estimator.decision_function(reference)
        raw_importances: list[float] = []
        for feature_index in range(reference.shape[1]):
            permuted = reference.copy()
            rng.shuffle(permuted[:, feature_index])
            permuted_scores = estimator.decision_function(permuted)
            impact = float(np.mean(np.abs(baseline_scores - permuted_scores)))
            raw_importances.append(impact)

        total_impact = sum(raw_importances)
        feature_names = get_feature_names()
        entries = [
            FeatureImportanceEntry(
                feature_name=feature_names[index],
                importance=(impact / total_impact) if total_impact else 0.0,
            )
            for index, impact in enumerate(raw_importances)
        ]
        return sorted(entries, key=lambda entry: entry.importance, reverse=True)

    @staticmethod
    def _top_contributing_features(
        scaled_vector: np.ndarray,
        loaded_model: LoadedAnomalyModel,
        *,
        limit: int = 5,
    ) -> list[FeatureImportanceEntry]:
        global_importance = {
            entry.feature_name: entry.importance for entry in loaded_model.feature_importances
        }
        contributions = [
            FeatureImportanceEntry(
                feature_name=feature_name,
                importance=float(abs(scaled_vector[index]) * (0.25 + global_importance.get(feature_name, 0.0))),
            )
            for index, feature_name in enumerate(loaded_model.feature_names)
        ]
        return sorted(contributions, key=lambda entry: entry.importance, reverse=True)[:limit]

    @staticmethod
    def _confidence_from_score(score: float) -> float:
        distance = abs(score)
        confidence = distance / (distance + 0.08)
        if math.isnan(confidence):
            return 0.0
        return float(max(0.0, min(1.0, confidence)))

    def _artifact_path(self, model_version: str) -> Path:
        return self.artifact_dir / f"{model_version}.joblib"

    def _metadata_path(self, model_version: str) -> Path:
        return self.artifact_dir / f"{model_version}.metadata.json"

    @staticmethod
    def _build_model_version(trained_at: datetime, run_id: uuid.UUID) -> str:
        timestamp = trained_at.strftime("%Y%m%dT%H%M%SZ")
        return f"iforest-{timestamp}-{str(run_id)[:8]}"

    @staticmethod
    def _metadata_from_artifact(artifact: dict[str, Any], artifact_path: Path) -> dict[str, Any]:
        return {
            "schema_version": artifact["schema_version"],
            "model_version": artifact["model_version"],
            "trained_at": artifact["trained_at"],
            "training_dataset_run_id": artifact["training_dataset_run_id"],
            "feature_count": artifact["feature_count"],
            "sample_count": artifact["sample_count"],
            "metrics": artifact["metrics"],
            "feature_importances": artifact["feature_importances"],
            "hyperparameters": artifact["hyperparameters"],
            "artifact_path": str(artifact_path),
        }

    def _write_current_pointer(self, model_version: str, artifact_path: Path) -> None:
        pointer_path = self.artifact_dir / CURRENT_POINTER_FILE
        pointer_path.write_text(
            json.dumps(
                {
                    "model_version": model_version,
                    "artifact_path": str(artifact_path),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=True,
                indent=2,
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _loaded_model_from_artifact(
        artifact: dict[str, Any],
        artifact_path: Path,
    ) -> LoadedAnomalyModel:
        if artifact.get("schema_version") != ARTIFACT_SCHEMA_VERSION:
            raise MLDatasetError(
                "Unsupported anomaly model artifact schema.",
                details={
                    "expected_schema_version": ARTIFACT_SCHEMA_VERSION,
                    "actual_schema_version": artifact.get("schema_version"),
                },
            )
        feature_names = list(artifact["feature_names"])
        if feature_names != get_feature_names():
            raise MLDatasetError(
                "Current feature schema does not match the loaded model artifact.",
                details={
                    "current_feature_count": get_feature_count(),
                    "artifact_feature_count": len(feature_names),
                },
            )
        return LoadedAnomalyModel(
            version=artifact["model_version"],
            trained_at=datetime.fromisoformat(artifact["trained_at"]),
            estimator=artifact["estimator"],
            scaler=artifact["scaler"],
            feature_names=feature_names,
            metrics=TrainingMetrics.model_validate(artifact["metrics"]),
            feature_importances=[
                FeatureImportanceEntry.model_validate(entry)
                for entry in artifact["feature_importances"]
            ],
            hyperparameters=dict(artifact["hyperparameters"]),
            sample_count=int(artifact["sample_count"]),
            artifact_path=artifact_path,
        )

    def _read_current_version(self) -> str | None:
        pointer_path = self.artifact_dir / CURRENT_POINTER_FILE
        if not pointer_path.exists():
            return None
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        return str(pointer.get("model_version")) if pointer.get("model_version") else None


_service: AnomalyDetectionService | None = None


def get_anomaly_detection_service() -> AnomalyDetectionService:
    global _service
    if _service is None:
        _service = AnomalyDetectionService()
    return _service
