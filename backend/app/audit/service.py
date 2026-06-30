from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pymongo.errors import DuplicateKeyError

from app.audit.hashing import build_entry_hash, build_merkle_leaf_hash
from app.audit.merkle import build_merkle_proof, compute_merkle_root, verify_merkle_proof
from app.core.exceptions import LedgerIntegrityError, NotFoundError
from app.core.logging import get_logger
from app.models.audit_ledger import AuditLedgerEntry

logger = get_logger(__name__)
LEDGER_APPEND_MAX_RETRIES = 3


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AuditLedgerService:
    """Append-only immutable ledger backed by a chained hash sequence in MongoDB."""

    @staticmethod
    def serialize_entry(entry: AuditLedgerEntry) -> dict[str, Any]:
        return {
            "entry_id": str(entry.id),
            "sequence_number": entry.sequence_number,
            "event_type": entry.event_type,
            "actor_type": entry.actor_type,
            "actor_id": entry.actor_id,
            "subject_type": entry.subject_type,
            "subject_id": entry.subject_id,
            "action_id": str(entry.action_id) if entry.action_id else None,
            "correlation_id": entry.correlation_id,
            "payload": entry.payload,
            "previous_hash": entry.previous_hash,
            "entry_hash": entry.entry_hash,
            "merkle_leaf_hash": entry.merkle_leaf_hash,
            "created_at": entry.created_at.isoformat(),
        }

    @classmethod
    async def append_entry(
        cls,
        *,
        event_type: str,
        payload: dict[str, Any],
        actor_type: str | None = None,
        actor_id: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
        action_id: uuid.UUID | None = None,
        correlation_id: str | None = None,
    ) -> AuditLedgerEntry:
        created_at = utc_now()
        last_error: Exception | None = None

        for attempt in range(1, LEDGER_APPEND_MAX_RETRIES + 1):
            try:
                # Event Sourcing: find the latest entry to build the next block in the chain
                latest_entry = await AuditLedgerEntry.find_all().sort(-AuditLedgerEntry.sequence_number).first_or_none()

                sequence_number = (latest_entry.sequence_number + 1) if latest_entry else 1
                previous_hash = latest_entry.entry_hash if latest_entry else None
                entry_hash = build_entry_hash(
                    sequence_number=sequence_number,
                    event_type=event_type,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    subject_type=subject_type,
                    subject_id=subject_id,
                    action_id=str(action_id) if action_id else None,
                    correlation_id=correlation_id,
                    payload=payload,
                    previous_hash=previous_hash,
                    created_at=created_at,
                )
                merkle_leaf_hash = build_merkle_leaf_hash(entry_hash)

                entry = AuditLedgerEntry(
                    id=uuid.uuid4(),
                    sequence_number=sequence_number,
                    event_type=event_type,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    subject_type=subject_type,
                    subject_id=subject_id,
                    action_id=action_id,
                    correlation_id=correlation_id,
                    payload=payload,
                    previous_hash=previous_hash,
                    entry_hash=entry_hash,
                    merkle_leaf_hash=merkle_leaf_hash,
                    created_at=created_at,
                )
                await entry.insert()
                logger.info(
                    "Audit ledger entry appended successfully",
                    event_type=event_type,
                    sequence_number=sequence_number,
                    append_attempt=attempt,
                )
                return entry
            except (DuplicateKeyError, Exception) as exc:
                last_error = exc
                logger.warning(
                    "Audit ledger append conflict detected",
                    event_type=event_type,
                    append_attempt=attempt,
                    max_retries=LEDGER_APPEND_MAX_RETRIES,
                    error=str(exc),
                )

        raise LedgerIntegrityError(
            "Unable to append audit ledger entry due to concurrent write contention.",
            details={"event_type": event_type, "attempts": LEDGER_APPEND_MAX_RETRIES},
        ) from last_error

    @classmethod
    async def search_entries(
        cls,
        *,
        session: Any = None,  # Kept for signature compatibility
        event_type: str | None = None,
        action_id: uuid.UUID | None = None,
        correlation_id: str | None = None,
        search: str | None = None,
        limit: int = 50,
    ) -> list[AuditLedgerEntry]:
        query: dict[str, Any] = {}
        if event_type:
            query["event_type"] = event_type
        if action_id:
            query["action_id"] = action_id
        if correlation_id:
            query["correlation_id"] = correlation_id
        if search:
            regex_search = {"$regex": search, "$options": "i"}
            query["$or"] = [
                {"event_type": regex_search},
                {"actor_id": regex_search},
                {"subject_id": regex_search},
                {"payload.message": regex_search},
                {"payload.reason": regex_search},
            ]

        return await AuditLedgerEntry.find(query).sort(-AuditLedgerEntry.sequence_number).limit(limit).to_list()

    @classmethod
    async def export_entries(
        cls,
        *,
        session: Any = None,
        event_type: str | None = None,
        action_id: uuid.UUID | None = None,
        correlation_id: str | None = None,
        search: str | None = None,
        limit: int = 500,
    ) -> dict[str, Any]:
        entries = await cls.search_entries(
            event_type=event_type,
            action_id=action_id,
            correlation_id=correlation_id,
            search=search,
            limit=limit,
        )
        ordered_entries = list(reversed(entries))
        merkle_root = compute_merkle_root([entry.merkle_leaf_hash for entry in ordered_entries])
        return {
            "count": len(ordered_entries),
            "merkle_root": merkle_root,
            "entries": [cls.serialize_entry(entry) for entry in ordered_entries],
        }

    @classmethod
    async def verify_ledger(cls, *, session: Any = None) -> dict[str, Any]:
        entries = await AuditLedgerEntry.find_all().sort(+AuditLedgerEntry.sequence_number).to_list()
        if not entries:
            return {"valid": True, "entries_checked": 0, "merkle_root": None}

        previous_hash: str | None = None
        leaf_hashes: list[str] = []
        for expected_sequence, entry in enumerate(entries, start=1):
            if entry.sequence_number != expected_sequence:
                raise LedgerIntegrityError(
                    "Ledger sequence gap detected.",
                    details={"expected": expected_sequence, "actual": entry.sequence_number},
                )
            if entry.previous_hash != previous_hash:
                raise LedgerIntegrityError(
                    "Ledger hash chain broken.",
                    details={"sequence_number": entry.sequence_number},
                )

            recomputed_hash = build_entry_hash(
                sequence_number=entry.sequence_number,
                event_type=entry.event_type,
                actor_type=entry.actor_type,
                actor_id=entry.actor_id,
                subject_type=entry.subject_type,
                subject_id=entry.subject_id,
                action_id=str(entry.action_id) if entry.action_id else None,
                correlation_id=entry.correlation_id,
                payload=entry.payload,
                previous_hash=entry.previous_hash,
                created_at=entry.created_at,
            )
            if recomputed_hash != entry.entry_hash:
                raise LedgerIntegrityError(
                    "Ledger entry hash mismatch detected.",
                    details={"sequence_number": entry.sequence_number},
                )

            recomputed_leaf = build_merkle_leaf_hash(entry.entry_hash)
            if recomputed_leaf != entry.merkle_leaf_hash:
                raise LedgerIntegrityError(
                    "Merkle leaf hash mismatch detected.",
                    details={"sequence_number": entry.sequence_number},
                )

            leaf_hashes.append(entry.merkle_leaf_hash)
            previous_hash = entry.entry_hash

        return {
            "valid": True,
            "entries_checked": len(entries),
            "head_entry_hash": entries[-1].entry_hash,
            "merkle_root": compute_merkle_root(leaf_hashes),
        }

    @classmethod
    async def build_entry_proof(cls, *, session: Any = None, entry_id: uuid.UUID) -> dict[str, Any]:
        entries = await AuditLedgerEntry.find_all().sort(+AuditLedgerEntry.sequence_number).to_list()
        if not entries:
            raise NotFoundError("Ledger is empty.")

        target_index = next((index for index, entry in enumerate(entries) if entry.id == entry_id), None)
        if target_index is None:
            raise NotFoundError(f"Ledger entry '{entry_id}' was not found.")

        target_entry = entries[target_index]
        merkle_root, siblings = build_merkle_proof(
            [entry.merkle_leaf_hash for entry in entries],
            target_index,
        )
        return {
            "entry": cls.serialize_entry(target_entry),
            "merkle_root": merkle_root,
            "proof": siblings,
        }

    @staticmethod
    def verify_entry_proof(*, leaf_hash: str, merkle_root: str, proof: list[dict[str, str]]) -> bool:
        return verify_merkle_proof(leaf_hash, proof, merkle_root)
