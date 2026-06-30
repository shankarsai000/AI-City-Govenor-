from pathlib import Path

import pytest

from app.simulator.models import SimulationRunRequest
from app.simulator.service import SyntheticCitySimulator


@pytest.mark.asyncio
async def test_simulator_generates_persisted_dataset(tmp_path: Path):
    simulator = SyntheticCitySimulator(output_dir=tmp_path)

    manifest = await simulator.run(
        SimulationRunRequest(
            target_log_count=120,
            seed=2026,
            anomaly_rate=0.05,
            persist_dataset=True,
            publish_summary_event=False,
        )
    )

    assert manifest.actual_log_count >= 120
    assert manifest.files.dataset_path is not None
    assert manifest.files.manifest_path is not None
    assert Path(manifest.files.dataset_path).exists()
    assert Path(manifest.files.manifest_path).exists()
    assert manifest.domain_distribution
    assert manifest.event_distribution
    assert manifest.sample_logs

    preview = simulator.read_dataset_preview(manifest.run_id, limit=15)
    assert len(preview) == 15
    assert all(entry.run_id == manifest.run_id for entry in preview)


@pytest.mark.asyncio
async def test_simulator_marks_anomalies_when_rate_is_high(tmp_path: Path):
    simulator = SyntheticCitySimulator(output_dir=tmp_path)

    manifest = await simulator.run(
        SimulationRunRequest(
            target_log_count=150,
            seed=2030,
            anomaly_rate=0.35,
            persist_dataset=False,
            publish_summary_event=False,
        )
    )

    anomaly_keys = {entry.key for entry in manifest.anomaly_distribution}
    assert any(key != "normal" for key in anomaly_keys)
