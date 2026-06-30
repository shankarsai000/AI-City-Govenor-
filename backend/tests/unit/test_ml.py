from pathlib import Path

import pytest

from app.core.exceptions import MLModelNotReadyError
from app.ml.features import extract_features, get_feature_names
from app.ml.models import PredictRequest, TrainRequest
from app.ml.service import AnomalyDetectionService
from app.simulator.models import SimulationRunRequest
from app.simulator.service import SyntheticCitySimulator


def test_feature_extraction_uses_stable_schema():
    feature_names = get_feature_names()
    features = extract_features(
        {
            "domain": "power",
            "event_type": "governance.action_requested",
            "action_type": "shed_load",
            "status": "submitted",
            "severity": "high",
            "timestamp": "2026-06-28T13:00:00+00:00",
            "payload": {"percentage": 18.5, "nested": {"count": 2}},
            "governance": {
                "risk_level": "high",
                "requires_human": True,
                "request_rate_per_minute": 4.2,
            },
            "security": {
                "signature_valid": True,
                "nonce_reuse_detected": False,
                "replay_risk_score": 0.04,
            },
        }
    )

    assert len(features) == len(feature_names)
    assert features[feature_names.index("domain_power")] == 1.0
    assert features[feature_names.index("action_shed_load")] == 1.0
    assert features[feature_names.index("event_governance_requested")] == 1.0
    assert features[feature_names.index("requires_human")] == 1.0
    assert features[feature_names.index("payload_numeric_count")] == 2.0


def test_predict_requires_trained_model(tmp_path: Path):
    service = AnomalyDetectionService(artifact_dir=tmp_path / "ml")

    with pytest.raises(MLModelNotReadyError):
        service.predict(PredictRequest(domain="traffic", action_type="reroute_traffic"))


@pytest.mark.asyncio
async def test_anomaly_service_trains_persists_and_reloads(tmp_path: Path):
    simulator = SyntheticCitySimulator(output_dir=tmp_path / "simulator")
    manifest = await simulator.run(
        SimulationRunRequest(
            target_log_count=180,
            seed=2042,
            anomaly_rate=0.12,
            persist_dataset=True,
            publish_summary_event=False,
        )
    )
    service = AnomalyDetectionService(
        artifact_dir=tmp_path / "ml",
        simulator=simulator,
    )

    result = service.train_from_simulation_run(
        TrainRequest(
            dataset_run_id=manifest.run_id,
            contamination=0.12,
            n_estimators=50,
            random_state=2042,
        )
    )

    assert Path(result.artifact_path).exists()
    assert result.metrics.total_samples == manifest.actual_log_count
    assert result.feature_count == len(get_feature_names())
    assert result.feature_importances

    prediction = service.assess_governance_action(
        domain="power",
        agent_name="power_agent",
        agent_id="agent-123",
        action_type="shed_load",
        payload={"zone": "north", "percentage": 24.5},
        risk_level="high",
        requires_human=True,
        policy_decision="allow",
    )
    assert prediction.model_version == result.model_version
    assert 0.0 <= prediction.confidence <= 1.0
    assert prediction.top_contributing_features

    reloaded_service = AnomalyDetectionService(
        artifact_dir=tmp_path / "ml",
        simulator=simulator,
    )
    reloaded_info = reloaded_service.get_model_info()
    assert reloaded_info.is_ready is True
    assert reloaded_info.model_version == result.model_version
