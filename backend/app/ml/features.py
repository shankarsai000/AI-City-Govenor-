"""Deterministic feature extraction for Stage 11 anomaly detection.

The ML layer consumes two kinds of records:
- simulator JSONL rows from Stage 10
- live governance action requests built inside the governance engine

Both are converted into the same ordered numeric vector. The model service then
owns scaling and Isolation Forest inference; request handlers never learn or
mutate feature schemas at runtime.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import numpy as np

DOMAINS: tuple[str, ...] = ("traffic", "power", "water", "emergency")

ACTIONS: tuple[str, ...] = (
    "reroute_traffic",
    "close_road",
    "activate_emergency_corridor",
    "load_balance",
    "shed_load",
    "emergency_shutdown",
    "adjust_pressure",
    "isolate_zone",
    "emergency_shutoff",
    "dispatch_unit",
    "declare_emergency",
    "request_mutual_aid",
)

STATUSES: tuple[str, ...] = (
    "detected",
    "assessed",
    "submitted",
    "pending",
    "approved",
    "rejected",
    "denied",
    "executed",
    "synced",
    "recorded",
    "failed",
)

EVENT_BUCKETS: tuple[str, ...] = (
    "sensor_detected",
    "agent_assessed",
    "governance_requested",
    "governance_approved",
    "governance_executed",
    "governance_denied",
    "approval",
    "city_state",
    "audit",
)

ORDINAL_LEVELS: dict[str, int] = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}

_FEATURE_NAMES: list[str] = (
    [f"domain_{domain}" for domain in DOMAINS]
    + [f"action_{action}" for action in ACTIONS]
    + [f"status_{status}" for status in STATUSES]
    + [f"event_{bucket}" for bucket in EVENT_BUCKETS]
    + [
        "severity_ordinal",
        "risk_level_ordinal",
        "requires_human",
        "request_rate_per_minute",
        "approval_latency_seconds",
        "signature_valid",
        "nonce_reuse_detected",
        "replay_risk_score",
        "hour_sin",
        "hour_cos",
        "is_weekend",
        "payload_numeric_count",
        "payload_numeric_mean",
        "payload_numeric_max",
        "payload_numeric_min",
        "telemetry_numeric_count",
        "telemetry_numeric_mean",
        "telemetry_numeric_max",
        "telemetry_numeric_min",
    ]
)


def get_feature_names() -> list[str]:
    """Return the ordered feature names used for training and inference."""

    return list(_FEATURE_NAMES)


def get_feature_count() -> int:
    """Return the number of features produced for every record."""

    return len(_FEATURE_NAMES)


def extract_features(log: Mapping[str, Any]) -> np.ndarray:
    """Convert a simulator or governance event into a 1-D numeric vector."""

    features = np.zeros(len(_FEATURE_NAMES), dtype=np.float64)
    write_index = 0

    write_index = _write_one_hot(
        features,
        write_index,
        values=DOMAINS,
        selected=str(log.get("domain", "")),
    )
    write_index = _write_one_hot(
        features,
        write_index,
        values=ACTIONS,
        selected=str(log.get("action_type", "")),
    )
    write_index = _write_one_hot(
        features,
        write_index,
        values=STATUSES,
        selected=str(log.get("status", "")),
    )
    write_index = _write_one_hot(
        features,
        write_index,
        values=EVENT_BUCKETS,
        selected=_event_bucket(str(log.get("event_type", ""))),
    )

    governance = _mapping(log.get("governance"))
    security = _mapping(log.get("security"))
    timestamp = _parse_datetime(log.get("timestamp"))
    payload = _mapping(log.get("payload"))
    telemetry = _mapping(log.get("telemetry"))

    features[write_index] = _ordinal(str(log.get("severity", "low")))
    write_index += 1
    features[write_index] = _ordinal(str(governance.get("risk_level", log.get("severity", "low"))))
    write_index += 1
    features[write_index] = 1.0 if governance.get("requires_human") else 0.0
    write_index += 1
    features[write_index] = _float(governance.get("request_rate_per_minute"))
    write_index += 1
    features[write_index] = _float(governance.get("approval_latency_seconds"))
    write_index += 1
    features[write_index] = 1.0 if security.get("signature_valid", True) else 0.0
    write_index += 1
    features[write_index] = 1.0 if security.get("nonce_reuse_detected", False) else 0.0
    write_index += 1
    features[write_index] = _float(security.get("replay_risk_score"))
    write_index += 1

    hour = float(timestamp.hour if timestamp else 12)
    features[write_index] = math.sin(2.0 * math.pi * hour / 24.0)
    write_index += 1
    features[write_index] = math.cos(2.0 * math.pi * hour / 24.0)
    write_index += 1
    features[write_index] = 1.0 if timestamp and timestamp.weekday() >= 5 else 0.0
    write_index += 1

    write_index = _write_numeric_summary(features, write_index, payload)
    _write_numeric_summary(features, write_index, telemetry)
    return features


def extract_features_batch(logs: list[Mapping[str, Any]]) -> np.ndarray:
    """Extract a 2-D feature matrix from a batch of logs."""

    if not logs:
        return np.empty((0, len(_FEATURE_NAMES)), dtype=np.float64)
    return np.vstack([extract_features(log) for log in logs])


def _write_one_hot(
    features: np.ndarray,
    start_index: int,
    *,
    values: tuple[str, ...],
    selected: str,
) -> int:
    try:
        selected_index = values.index(selected)
    except ValueError:
        return start_index + len(values)

    features[start_index + selected_index] = 1.0
    return start_index + len(values)


def _write_numeric_summary(
    features: np.ndarray,
    start_index: int,
    data: Mapping[str, Any],
) -> int:
    values = _numeric_values(data)
    if values:
        features[start_index] = float(len(values))
        features[start_index + 1] = float(np.mean(values))
        features[start_index + 2] = float(np.max(values))
        features[start_index + 3] = float(np.min(values))
    return start_index + 4


def _event_bucket(event_type: str) -> str:
    if event_type.endswith(".sensor_detected"):
        return "sensor_detected"
    if event_type.endswith(".agent_assessed"):
        return "agent_assessed"
    if event_type == "governance.action_requested":
        return "governance_requested"
    if event_type == "governance.action_approved":
        return "governance_approved"
    if event_type == "governance.action_executed":
        return "governance_executed"
    if event_type == "governance.action_denied":
        return "governance_denied"
    if event_type.startswith("approval."):
        return "approval"
    if event_type.startswith("city."):
        return "city_state"
    if event_type.startswith("audit."):
        return "audit"
    return ""


def _ordinal(value: str) -> float:
    return float(ORDINAL_LEVELS.get(value, 0))


def _float(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _numeric_values(value: Any) -> list[float]:
    values: list[float] = []
    if isinstance(value, Mapping):
        for nested_value in value.values():
            values.extend(_numeric_values(nested_value))
    elif isinstance(value, list):
        for nested_value in value:
            values.extend(_numeric_values(nested_value))
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        values.append(float(value))
    return values
