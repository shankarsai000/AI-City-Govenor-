from __future__ import annotations

import json
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from random import Random
from typing import Any

from app.city_state.domains import DOMAIN_STATE_TYPES
from app.city_state.mutations import MUTATION_REGISTRY
from app.config import get_settings
from app.core.event_bus import publish_event
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.simulator.catalog import SCENARIO_LIBRARY, ScenarioTemplate
from app.simulator.models import (
    SimulationDatasetFiles,
    SimulationDistributionEntry,
    SimulationRunManifest,
    SimulationRunRequest,
    SyntheticOperationLog,
)

logger = get_logger(__name__)


@dataclass
class SyntheticWorldState:
    """In-memory digital twin used only for simulator dataset generation."""

    domain_states: dict[str, Any]
    global_version: int
    domain_versions: dict[str, int]

    @classmethod
    def create(cls) -> SyntheticWorldState:
        return cls(
            domain_states={domain: state_cls() for domain, state_cls in DOMAIN_STATE_TYPES.items()},
            global_version=0,
            domain_versions={domain: 0 for domain in DOMAIN_STATE_TYPES},
        )

    def apply_action(
        self,
        *,
        domain: str,
        action_type: str,
        payload: dict[str, Any],
        timestamp: datetime,
    ) -> tuple[Any, int, int]:
        mutation_fn = MUTATION_REGISTRY[action_type]
        new_state = mutation_fn(self.domain_states[domain], payload)
        next_domain_version = self.domain_versions[domain] + 1
        self.global_version += 1
        self.domain_versions[domain] = next_domain_version

        state_dict = new_state.model_dump(mode="json")
        state_dict["version"] = next_domain_version
        state_dict["updated_at"] = timestamp.isoformat()
        validated_state = DOMAIN_STATE_TYPES[domain].model_validate(state_dict)
        self.domain_states[domain] = validated_state
        return validated_state, next_domain_version, self.global_version


class SyntheticCitySimulator:
    """Generates high-volume synthetic smart-city operations datasets."""

    def __init__(self, *, output_dir: Path | None = None) -> None:
        settings = get_settings()
        self.output_dir = output_dir or settings.SIMULATOR_OUTPUT_DIR

    async def run(self, request: SimulationRunRequest) -> SimulationRunManifest:
        run_id = uuid.uuid4()
        started_at = datetime.now(timezone.utc)
        randomizer = Random(request.seed)
        world_state = SyntheticWorldState.create()
        logs: list[SyntheticOperationLog] = []
        simulated_time = started_at - timedelta(hours=12)
        scenarios = self._filter_scenarios(request.include_domains)

        logger.info(
            "Starting synthetic city simulation run",
            run_id=str(run_id),
            target_log_count=request.target_log_count,
            anomaly_rate=request.anomaly_rate,
            domains=request.include_domains,
        )

        while len(logs) < request.target_log_count:
            scenario = self._choose_scenario(randomizer, scenarios)
            operation_logs, simulated_time = self._generate_operation(
                run_id=run_id,
                scenario=scenario,
                randomizer=randomizer,
                world_state=world_state,
                simulated_time=simulated_time,
                anomaly_rate=request.anomaly_rate,
            )
            logs.extend(operation_logs)

        completed_at = simulated_time
        manifest = SimulationRunManifest(
            run_id=run_id,
            seed=request.seed,
            anomaly_rate=request.anomaly_rate,
            requested_log_count=request.target_log_count,
            actual_log_count=len(logs),
            include_domains=request.include_domains,
            started_at=started_at,
            completed_at=completed_at,
            files=SimulationDatasetFiles(),
            domain_distribution=self._build_distribution(log.domain for log in logs),
            event_distribution=self._build_distribution(log.event_type for log in logs),
            anomaly_distribution=self._build_distribution(
                label for log in logs for label in (log.labels or ["normal"])
            ),
            sample_logs=logs[:10],
        )

        if request.persist_dataset:
            manifest = self._persist_run(manifest, logs)

        if request.publish_summary_event:
            await self._publish_summary_event(manifest)

        logger.info(
            "Synthetic city simulation run completed",
            run_id=str(run_id),
            actual_log_count=len(logs),
            dataset_path=manifest.files.dataset_path,
        )
        return manifest

    def list_runs(self, *, limit: int = 20) -> list[SimulationRunManifest]:
        manifests: list[SimulationRunManifest] = []
        for manifest_path in sorted(
            self.output_dir.glob("*.manifest.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )[:limit]:
            manifests.append(self._read_manifest(manifest_path))
        return manifests

    def get_run(self, run_id: uuid.UUID) -> SimulationRunManifest:
        manifest_path = self._manifest_path(run_id)
        if not manifest_path.exists():
            raise NotFoundError(f"Simulation run '{run_id}' was not found.")
        return self._read_manifest(manifest_path)

    def read_dataset_preview(
        self,
        run_id: uuid.UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SyntheticOperationLog]:
        dataset_path = self._dataset_path(run_id)
        if not dataset_path.exists():
            raise NotFoundError(f"Dataset for simulation run '{run_id}' was not found.")

        preview: list[SyntheticOperationLog] = []
        with dataset_path.open("r", encoding="utf-8") as file_handle:
            for index, line in enumerate(file_handle):
                if index < offset:
                    continue
                if len(preview) >= limit:
                    break
                preview.append(SyntheticOperationLog.model_validate_json(line))
        return preview

    def _filter_scenarios(self, include_domains: list[str]) -> list[ScenarioTemplate]:
        scenarios = [scenario for scenario in SCENARIO_LIBRARY if scenario.domain in include_domains]
        if not scenarios:
            raise ValueError("No simulator scenarios available for the selected domains.")
        return scenarios

    @staticmethod
    def _choose_scenario(randomizer: Random, scenarios: list[ScenarioTemplate]) -> ScenarioTemplate:
        total_weight = sum(scenario.weight for scenario in scenarios)
        threshold = randomizer.uniform(0, total_weight)
        cumulative = 0.0
        for scenario in scenarios:
            cumulative += scenario.weight
            if cumulative >= threshold:
                return scenario
        return scenarios[-1]

    def _generate_operation(
        self,
        *,
        run_id: uuid.UUID,
        scenario: ScenarioTemplate,
        randomizer: Random,
        world_state: SyntheticWorldState,
        simulated_time: datetime,
        anomaly_rate: float,
    ) -> tuple[list[SyntheticOperationLog], datetime]:
        operation_id = uuid.uuid4()
        payload = scenario.payload_factory(randomizer)
        base_telemetry = scenario.telemetry_factory(randomizer)
        location = scenario.location_factory(randomizer)
        anomalous = randomizer.random() < anomaly_rate
        anomaly_labels = self._build_anomaly_labels(randomizer, scenario, anomalous)
        decision = self._determine_decision(randomizer, scenario, anomalous, anomaly_labels)
        approval_latency_seconds = self._approval_latency_seconds(randomizer, scenario, anomalous, anomaly_labels)
        request_rate = self._request_rate(randomizer, anomalous, anomaly_labels)
        security_context = self._security_context(randomizer, anomalous, anomaly_labels)
        audit_context = self._audit_context(operation_id, scenario, anomalous)
        policy_outcome = self._policy_outcome(decision, anomalous, anomaly_labels)

        current_time = simulated_time + timedelta(seconds=randomizer.randint(15, 180))
        logs: list[SyntheticOperationLog] = []

        def append_log(
            *,
            event_type: str,
            status: str,
            message: str,
            severity: str,
            telemetry: dict[str, Any] | None = None,
            governance: dict[str, Any] | None = None,
            audit: dict[str, Any] | None = None,
            actor_id: str | None = None,
        ) -> None:
            nonlocal current_time
            logs.append(
                SyntheticOperationLog(
                    run_id=run_id,
                    operation_id=operation_id,
                    timestamp=current_time,
                    domain=scenario.domain,
                    scenario_id=scenario.scenario_id,
                    event_type=event_type,
                    severity=severity,  # type: ignore[arg-type]
                    source=scenario.source,
                    actor_id=actor_id or scenario.source,
                    location=location,
                    action_type=scenario.action_type,
                    status=status,
                    message=message,
                    telemetry=telemetry or {},
                    governance=governance or {},
                    security=security_context,
                    audit=audit or audit_context,
                    labels=anomaly_labels,
                    anomalous=anomalous,
                )
            )
            current_time = current_time + timedelta(seconds=randomizer.randint(5, 40))

        append_log(
            event_type=f"{scenario.domain}.sensor_detected",
            status="detected",
            message=scenario.description,
            severity=scenario.severity,
            telemetry=base_telemetry,
            governance={
                "risk_level": scenario.risk_level,
                "requires_human": scenario.requires_human,
                "policy_outcome": "observed",
                "request_rate_per_minute": request_rate,
            },
        )
        append_log(
            event_type=f"{scenario.domain}.agent_assessed",
            status="assessed",
            message=f"{scenario.source} assessed telemetry and prepared action '{scenario.action_type}'.",
            severity=scenario.severity,
            telemetry=base_telemetry,
            governance={
                "risk_level": scenario.risk_level,
                "requires_human": scenario.requires_human,
                "policy_outcome": "assessed",
                "request_rate_per_minute": request_rate,
            },
        )
        append_log(
            event_type="governance.action_requested",
            status="submitted",
            message=f"Governance received action request '{scenario.action_type}'.",
            severity=scenario.risk_level,
            governance={
                "risk_level": scenario.risk_level,
                "requires_human": scenario.requires_human,
                "decision": "pending",
                "policy_outcome": "submitted",
                "request_rate_per_minute": request_rate,
            },
        )

        if scenario.requires_human:
            append_log(
                event_type="approval.created",
                status="pending",
                message="Approval queue item created for human oversight.",
                severity=scenario.risk_level,
                governance={
                    "risk_level": scenario.risk_level,
                    "requires_human": True,
                    "decision": "pending",
                    "approval_latency_seconds": approval_latency_seconds,
                    "policy_outcome": "approval_required",
                },
                actor_id="governance_engine",
            )
            append_log(
                event_type=f"approval.{decision}",
                status=decision,
                message=f"Human oversight completed with decision '{decision}'.",
                severity=scenario.risk_level,
                governance={
                    "risk_level": scenario.risk_level,
                    "requires_human": True,
                    "decision": decision,
                    "approval_latency_seconds": approval_latency_seconds,
                    "policy_outcome": policy_outcome,
                },
                actor_id="operator_console" if decision == "approved" else "auditor_console",
            )
        else:
            append_log(
                event_type="governance.action_approved",
                status="approved",
                message="Low-risk action auto-approved by governance policy.",
                severity=scenario.risk_level,
                governance={
                    "risk_level": scenario.risk_level,
                    "requires_human": False,
                    "decision": "approved",
                    "approval_latency_seconds": 0,
                    "policy_outcome": policy_outcome,
                    "request_rate_per_minute": request_rate,
                },
                actor_id="governance_engine",
            )
            decision = "approved"

        if decision == "approved":
            validated_state, domain_version, global_version = world_state.apply_action(
                domain=scenario.domain,
                action_type=scenario.action_type,
                payload=payload,
                timestamp=current_time,
            )
            state_summary = self._summarize_state(scenario.domain, validated_state)
            append_log(
                event_type="governance.action_executed",
                status="executed",
                message=f"Action '{scenario.action_type}' executed successfully.",
                severity=scenario.risk_level,
                telemetry=state_summary,
                governance={
                    "risk_level": scenario.risk_level,
                    "requires_human": scenario.requires_human,
                    "decision": "approved",
                    "policy_outcome": "executed",
                    "domain_version": domain_version,
                    "global_version": global_version,
                },
                actor_id="governance_engine",
            )
            append_log(
                event_type="city.state_changed",
                status="synced",
                message="Digital twin synchronized after approved action.",
                severity=scenario.severity,
                telemetry=state_summary,
                governance={
                    "domain_version": domain_version,
                    "global_version": global_version,
                    "action_type": scenario.action_type,
                },
                actor_id="city_state_engine",
            )
        else:
            append_log(
                event_type="governance.action_denied",
                status="denied",
                message=f"Action '{scenario.action_type}' was denied by governance controls.",
                severity=scenario.risk_level,
                governance={
                    "risk_level": scenario.risk_level,
                    "requires_human": scenario.requires_human,
                    "decision": "rejected",
                    "policy_outcome": policy_outcome,
                },
                actor_id="governance_engine",
            )

        append_log(
            event_type="audit.synthetic_recorded",
            status="recorded",
            message="Synthetic training log committed to simulator dataset.",
            severity="low",
            audit={
                **audit_context,
                "synthetic_only": True,
                "approved": decision == "approved",
            },
            actor_id="simulator_engine",
        )

        return logs, current_time

    @staticmethod
    def _build_anomaly_labels(
        randomizer: Random,
        scenario: ScenarioTemplate,
        anomalous: bool,
    ) -> list[str]:
        if not anomalous:
            return []

        labels = [
            "abnormal_action_frequency",
            "suspicious_nonce_reuse",
            "outlier_approval_latency",
            "policy_conflict",
            "after_hours_operation",
        ]
        primary = labels[randomizer.randrange(0, len(labels))]
        result = [primary]
        if scenario.requires_human and randomizer.random() < 0.25:
            result.append("outlier_decision_path")
        return result

    @staticmethod
    def _determine_decision(
        randomizer: Random,
        scenario: ScenarioTemplate,
        anomalous: bool,
        anomaly_labels: list[str],
    ) -> str:
        if not scenario.requires_human:
            return "approved"
        if not anomalous:
            return "approved" if randomizer.random() < 0.88 else "rejected"
        if "policy_conflict" in anomaly_labels or "suspicious_nonce_reuse" in anomaly_labels:
            return "rejected"
        return "approved" if randomizer.random() < 0.45 else "rejected"

    @staticmethod
    def _approval_latency_seconds(
        randomizer: Random,
        scenario: ScenarioTemplate,
        anomalous: bool,
        anomaly_labels: list[str],
    ) -> int:
        if not scenario.requires_human:
            return 0
        if anomalous and "outlier_approval_latency" in anomaly_labels:
            return randomizer.randint(1, 20) if randomizer.random() < 0.5 else randomizer.randint(1_200, 4_200)
        return randomizer.randint(45, 720)

    @staticmethod
    def _request_rate(randomizer: Random, anomalous: bool, anomaly_labels: list[str]) -> float:
        if anomalous and "abnormal_action_frequency" in anomaly_labels:
            return round(randomizer.uniform(18.0, 54.0), 2)
        return round(randomizer.uniform(0.4, 8.5), 2)

    @staticmethod
    def _security_context(randomizer: Random, anomalous: bool, anomaly_labels: list[str]) -> dict[str, Any]:
        nonce_reuse = anomalous and "suspicious_nonce_reuse" in anomaly_labels
        return {
            "signature_valid": not nonce_reuse,
            "nonce_reuse_detected": nonce_reuse,
            "replay_risk_score": round(randomizer.uniform(0.01, 0.18), 3) if not nonce_reuse else round(randomizer.uniform(0.82, 0.99), 3),
        }

    @staticmethod
    def _audit_context(operation_id: uuid.UUID, scenario: ScenarioTemplate, anomalous: bool) -> dict[str, Any]:
        return {
            "trace_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"simulator:{operation_id}")),
            "chain_position_hint": scenario.scenario_id,
            "tamper_evident": True,
            "retention_tier": "synthetic_training",
            "anomaly_flagged": anomalous,
        }

    @staticmethod
    def _policy_outcome(decision: str, anomalous: bool, anomaly_labels: list[str]) -> str:
        if not anomalous:
            return "approved" if decision == "approved" else "rejected"
        if "policy_conflict" in anomaly_labels:
            return "escalated_conflict"
        if "suspicious_nonce_reuse" in anomaly_labels:
            return "security_blocked"
        return "approved_with_warning" if decision == "approved" else "rejected"

    @staticmethod
    def _summarize_state(domain: str, state: Any) -> dict[str, Any]:
        if domain == "traffic":
            return {
                "congestion_level": state.congestion_level,
                "active_corridors": len(state.active_corridors),
                "closed_roads": len(state.closed_roads),
                "version": state.version,
            }
        if domain == "power":
            return {
                "grid_load_mw": state.grid_load_mw,
                "capacity_mw": state.capacity_mw,
                "blackout_zones": len(state.blackout_zones),
                "active_shedding": len(state.active_shedding),
                "version": state.version,
            }
        if domain == "water":
            return {
                "pressure_psi": state.pressure_psi,
                "active_isolations": len(state.active_isolations),
                "leak_zones": len(state.leak_zones),
                "version": state.version,
            }
        return {
            "alert_level": state.alert_level,
            "active_incidents": len(state.active_incidents),
            "dispatched_units": len(state.dispatched_units),
            "version": state.version,
        }

    @staticmethod
    def _build_distribution(values: Any) -> list[SimulationDistributionEntry]:
        counter = Counter(values)
        return [
            SimulationDistributionEntry(key=str(key), count=count)
            for key, count in counter.most_common()
        ]

    def _persist_run(
        self,
        manifest: SimulationRunManifest,
        logs: list[SyntheticOperationLog],
    ) -> SimulationRunManifest:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = self._manifest_path(manifest.run_id)
        dataset_path = self._dataset_path(manifest.run_id)

        with dataset_path.open("w", encoding="utf-8") as file_handle:
            for log in logs:
                file_handle.write(log.model_dump_json())
                file_handle.write("\n")

        persisted_manifest = manifest.model_copy(
            update={
                "files": SimulationDatasetFiles(
                    manifest_path=str(manifest_path),
                    dataset_path=str(dataset_path),
                )
            }
        )
        manifest_path.write_text(
            json.dumps(persisted_manifest.model_dump(mode="json"), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
        return persisted_manifest

    async def _publish_summary_event(self, manifest: SimulationRunManifest) -> None:
        try:
            await publish_event(
                event_type="simulator.run_completed",
                source_agent="synthetic_city_simulator",
                payload={
                    "run_id": str(manifest.run_id),
                    "actual_log_count": manifest.actual_log_count,
                    "domains": manifest.include_domains,
                    "dataset_path": manifest.files.dataset_path,
                },
            )
        except Exception as exc:
            logger.warning(
                "Failed to publish simulator summary event",
                run_id=str(manifest.run_id),
                error=str(exc),
            )

    def _manifest_path(self, run_id: uuid.UUID) -> Path:
        return self.output_dir / f"{run_id}.manifest.json"

    def _dataset_path(self, run_id: uuid.UUID) -> Path:
        return self.output_dir / f"{run_id}.dataset.jsonl"

    @staticmethod
    def _read_manifest(path: Path) -> SimulationRunManifest:
        return SimulationRunManifest.model_validate_json(path.read_text(encoding="utf-8"))
