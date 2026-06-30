"""
State manager for the City State Engine.

Orchestrates read/write paths for the city's digital twin:
- Hot layer: Redis cache for sub-millisecond access.
- Cold layer: MongoDB for transactional history and recovery.
- Event Sourcing: State is projected to Redis and MongoDB from the audit log.
- Uses distributed locks to synchronize concurrent updates.
- Evaluates proposed changes against physical constraints using ConflictDetector.
"""
from typing import Any
import uuid
from datetime import datetime, timezone

from app.core.redis_client import get_redis
from app.core.event_bus import publish_event
from app.core.logging import get_logger
from app.core.exceptions import (
    ActionValidationError,
    ConflictDetectedError,
    ResourceLockError,
)
from app.city_state.domains import (
    CityState,
    CityStateSyncStatus,
    DOMAIN_STATE_TYPES,
)
from app.city_state.resource_lock import ResourceLock
from app.city_state.conflict_detector import ConflictDetector
from app.city_state.conflict_resolver import ConflictResolver
from app.city_state.mutations import MUTATION_REGISTRY, build_state_mutation
logger = get_logger(__name__)

REDIS_STATE_PREFIX = "city:state"
MUTATION_LOCK_PREFIX = "city:state_mutate"
STATE_META_KEY = f"{REDIS_STATE_PREFIX}:meta"


class CityStateManager:
    """Manages the lifecycle and state mutations of the smart city twin using event sourcing."""

    @staticmethod
    def _get_redis_key(domain: str) -> str:
        return f"{REDIS_STATE_PREFIX}:{domain}"

    @staticmethod
    def _default_sync_status() -> CityStateSyncStatus:
        return CityStateSyncStatus()

    @classmethod
    async def _read_sync_status(cls) -> CityStateSyncStatus:
        redis = get_redis()
        raw_status = await redis.get(STATE_META_KEY)
        if not raw_status:
            return cls._default_sync_status()

        try:
            return CityStateSyncStatus.model_validate_json(raw_status)
        except Exception as exc:
            logger.warning("Falling back to default city sync status", error=str(exc))
            return cls._default_sync_status()

    @classmethod
    async def _write_sync_status(cls, status: CityStateSyncStatus) -> None:
        redis = get_redis()
        await redis.set(STATE_META_KEY, status.model_dump_json())

    @classmethod
    async def _acquire_mutation_locks(cls, domain: str, resources: list[str], holder: str) -> list[str]:
        lock_ids = [f"{MUTATION_LOCK_PREFIX}:{domain}", *resources]
        acquired_locks: list[str] = []

        for lock_id in lock_ids:
            acquired = await ResourceLock.acquire(lock_id, holder=holder, ttl_seconds=15)
            if not acquired:
                await cls._release_mutation_locks(acquired_locks, holder)
                raise ResourceLockError(
                    f"Resource '{lock_id}' is currently locked by another operation.",
                    details={"lock_id": lock_id, "affected_resources": resources},
                )
            acquired_locks.append(lock_id)

        return acquired_locks

    @staticmethod
    async def _release_mutation_locks(lock_ids: list[str], holder: str) -> None:
        for lock_id in reversed(lock_ids):
            await ResourceLock.release(lock_id, holder=holder)

    @classmethod
    async def initialize(cls) -> None:
        """
        Seed default states in Redis and MongoDB if not already initialized.
        Called once at application lifespan startup.
        """
        redis = get_redis()
        logger.info("Initializing CityStateManager baseline...")

        # Ensure digital twin exists
        from app.models.digital_twin import CityDigitalTwin
        from app.models.city_state_snapshot import CityStateSnapshot
        twin = await CityDigitalTwin.find_all().first_or_none()
        if not twin:
            twin = CityDigitalTwin(version=0)
            await twin.insert()
            logger.info("Initialized blank CityDigitalTwin in MongoDB")

        for domain, state_cls in DOMAIN_STATE_TYPES.items():
            key = cls._get_redis_key(domain)
            exists = await redis.exists(key)
            if not exists:
                default_state = state_cls()
                # Store default state as serialized JSON in Redis
                await redis.set(key, default_state.model_dump_json())
                logger.info("Seeded default state in Redis", domain=domain)

                # Set corresponding domain on digital twin if it's default
                setattr(twin, domain, default_state)

                # Insert initial baseline snapshot in MongoDB (cold storage)
                snapshot_exists = await CityStateSnapshot.find_one(
                    CityStateSnapshot.domain == domain, CityStateSnapshot.version == 0
                )
                if not snapshot_exists:
                    snapshot = CityStateSnapshot(
                        id=uuid.uuid4(),
                        domain=domain,
                        state_data=default_state.model_dump(mode="json"),
                        version=0,
                        triggered_by="initial_seed",
                        action_id=None,
                    )
                    await snapshot.insert()
                    logger.info("Seeded default snapshot in MongoDB", domain=domain)

        await twin.save()

        if not await redis.exists(STATE_META_KEY):
            await cls._write_sync_status(cls._default_sync_status())
            logger.info("Seeded city sync metadata")

    @classmethod
    async def get_sync_status(cls) -> CityStateSyncStatus:
        """Return the current city-state synchronization metadata."""
        sync_status = await cls._read_sync_status()
        sync_status.active_locks = await ResourceLock.get_all_locks()
        return sync_status

    @classmethod
    async def get_domain_state(cls, domain: str) -> Any:
        """Fetch current state of a single domain from Redis."""
        if domain not in DOMAIN_STATE_TYPES:
            raise ValueError(f"Unknown domain: {domain}")

        redis = get_redis()
        key = cls._get_redis_key(domain)
        data = await redis.get(key)

        state_cls = DOMAIN_STATE_TYPES[domain]
        if not data:
            return state_cls()

        try:
            return state_cls.model_validate_json(data)
        except Exception as e:
            logger.error("Failed to parse domain state from Redis", domain=domain, error=str(e))
            return state_cls()

    @classmethod
    async def get_full_state(cls) -> CityState:
        """Get the full composite CityState from Redis."""
        traffic = await cls.get_domain_state("traffic")
        power = await cls.get_domain_state("power")
        water = await cls.get_domain_state("water")
        emergency = await cls.get_domain_state("emergency")
        sync_status = await cls._read_sync_status()

        return CityState(
            traffic=traffic,
            power=power,
            water=water,
            emergency=emergency,
            version=sync_status.global_version,
            updated_at=sync_status.updated_at,
        )

    @classmethod
    async def apply_mutation(
        cls, domain: str, action_type: str, payload: dict[str, Any], action_id: uuid.UUID | None = None
    ) -> Any:
        """
        Applies a state mutation dynamically using lock, validation,
        conflict resolution, and hot/cold database syncing.
        """
        if domain not in DOMAIN_STATE_TYPES:
            raise ValueError(f"Unknown domain: {domain}")

        mutation_fn = MUTATION_REGISTRY.get(action_type)
        if not mutation_fn:
            raise ActionValidationError(f"Unsupported state mutation action '{action_type}'.")

        mutation = build_state_mutation(action_type, payload)
        if mutation.domain != domain:
            raise ActionValidationError(
                f"Action '{action_type}' is bound to domain '{mutation.domain}', not '{domain}'."
            )

        lock_holder = f"state_manager_{action_type}"
        acquired_locks = await cls._acquire_mutation_locks(
            domain=domain,
            resources=mutation.affected_resources,
            holder=lock_holder,
        )

        try:
            # 2. Get current state
            current_state = await cls.get_full_state()
            current_domain_state = getattr(current_state, domain)

            # 3. Detect and resolve conflicts
            conflicts = await ConflictDetector.check(domain, mutation, current_state)
            resolution = await ConflictResolver.resolve(conflicts, mutation)

            if resolution.action == "block":
                logger.error("State mutation blocked due to physical conflict", conflicts=conflicts)
                raise ConflictDetectedError(
                    f"Action blocked: {resolution.reason}",
                    details={"conflicts": [c.model_dump() for c in conflicts]},
                )

            elif resolution.action == "escalate":
                logger.warning("State mutation requires escalation", conflicts=conflicts)
                raise ActionValidationError(
                    f"Physical warning: {resolution.reason}", details={"conflicts": [c.model_dump() for c in conflicts]}
                )

            # 4. Apply mutation and increment version
            new_domain_state = mutation_fn(current_domain_state, payload)
            mutation_timestamp = datetime.now(timezone.utc)
            sync_status = await cls._read_sync_status()

            current_version = getattr(current_domain_state, "version", 0)
            new_version = current_version + 1

            # Serialize updates back
            redis = get_redis()
            state_key = cls._get_redis_key(domain)

            state_dict = new_domain_state.model_dump()
            state_dict["version"] = new_version
            state_dict["updated_at"] = mutation_timestamp.isoformat()

            # Re-serialize model with new version metadata
            validated_state = DOMAIN_STATE_TYPES[domain].model_validate(state_dict)
            await redis.set(state_key, validated_state.model_dump_json())

            sync_status.global_version += 1
            sync_status.updated_at = mutation_timestamp
            sync_status.domain_versions[domain] = new_version
            await cls._write_sync_status(sync_status)

            # 5. Persist to MongoDB Projection Snapshot
            from app.models.city_state_snapshot import CityStateSnapshot
            snapshot = CityStateSnapshot(
                id=uuid.uuid4(),
                domain=domain,
                state_data=validated_state.model_dump(mode="json"),
                version=new_version,
                triggered_by=action_type,
                action_id=action_id,
            )
            await snapshot.insert()

            # Update MongoDB Digital Twin Projection
            from app.models.digital_twin import CityDigitalTwin
            twin = await CityDigitalTwin.find_all().first_or_none()
            if not twin:
                twin = CityDigitalTwin(version=0)
                await twin.insert()
            setattr(twin, domain, validated_state)
            twin.updated_at = mutation_timestamp
            twin.version = sync_status.global_version
            await twin.save()

            # 6. Publish real-time state change event
            state_payload = {
                "domain": domain,
                "action_type": action_type,
                "global_version": sync_status.global_version,
                "version": new_version,
                "timestamp": mutation_timestamp.isoformat(),
                "affected_resources": mutation.affected_resources,
                "state": validated_state.model_dump(mode="json"),
            }
            await publish_event(
                event_type="city.state_changed",
                source_agent="city_state_engine",
                payload=state_payload,
            )

            # Event Sourcing Append
            from app.audit.service import AuditLedgerService
            await AuditLedgerService.append_entry(
                event_type="city.state_changed",
                actor_type="system",
                actor_id="city_state_engine",
                subject_type="domain",
                subject_id=domain,
                action_id=action_id,
                payload=state_payload,
            )

            logger.info("Successfully applied state mutation", domain=domain, action=action_type, version=new_version)
            return validated_state

        finally:
            # 7. Always release mutex lock
            await cls._release_mutation_locks(acquired_locks, holder=lock_holder)

    @classmethod
    async def rebuild_from_events(cls) -> None:
        """
        Event Sourcing Replay: Rebuilds Redis states, Digital Twin projection,
        and state snapshots from the immutable audit ledger.
        """
        logger.info("Starting Event Sourcing replay to rebuild projections...")

        # 1. Reset hot layer (Redis)
        redis = get_redis()
        for domain in DOMAIN_STATE_TYPES:
            await redis.delete(cls._get_redis_key(domain))
        await redis.delete(STATE_META_KEY)

        # 2. Reset cold projections (MongoDB)
        from app.models.digital_twin import CityDigitalTwin
        from app.models.city_state_snapshot import CityStateSnapshot
        await CityStateSnapshot.find_all().delete()
        await CityDigitalTwin.find_all().delete()

        # 3. Seed default base states
        twin = CityDigitalTwin(version=0)
        await twin.insert()

        sync_status = cls._default_sync_status()
        for domain, state_cls in DOMAIN_STATE_TYPES.items():
            key = cls._get_redis_key(domain)
            default_state = state_cls()
            await redis.set(key, default_state.model_dump_json())

            snapshot = CityStateSnapshot(
                id=uuid.uuid4(),
                domain=domain,
                state_data=default_state.model_dump(mode="json"),
                version=0,
                triggered_by="initial_seed",
                action_id=None,
            )
            await snapshot.insert()
            setattr(twin, domain, default_state)

        await twin.save()
        await cls._write_sync_status(sync_status)

        # 4. Fetch and replay all state change events
        from app.models.audit_ledger import AuditLedgerEntry
        events = await AuditLedgerEntry.find({"event_type": "city.state_changed"}).sort("+AuditLedgerEntry.sequence_number").to_list()
        logger.info(f"Replaying {len(events)} state change events...")

        for event in events:
            payload_data = event.payload
            domain = payload_data.get("domain")
            action_type = payload_data.get("action_type")
            state_data = payload_data.get("state")
            global_version = payload_data.get("global_version", 0)
            version = payload_data.get("version", 0)
            timestamp_str = payload_data.get("timestamp")
            timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else event.created_at

            if not domain or not action_type or not state_data:
                continue

            state_cls = DOMAIN_STATE_TYPES[domain]
            validated_state = state_cls.model_validate(state_data)

            # Update Redis
            await redis.set(cls._get_redis_key(domain), validated_state.model_dump_json())

            # Update snapshots collection
            snapshot = CityStateSnapshot(
                id=uuid.uuid4(),
                domain=domain,
                state_data=state_data,
                version=version,
                triggered_by=action_type,
                action_id=event.action_id,
                created_at=timestamp,
            )
            await snapshot.insert()

            # Update digital twin
            setattr(twin, domain, validated_state)
            twin.updated_at = timestamp
            twin.version = global_version
            await twin.save()

            # Update sync metadata
            sync_status.global_version = global_version
            sync_status.updated_at = timestamp
            sync_status.domain_versions[domain] = version
            await cls._write_sync_status(sync_status)

        logger.info("Projections successfully reconstructed from event stream")
