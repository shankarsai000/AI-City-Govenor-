from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from app.audit.hashing import build_entry_hash, build_merkle_leaf_hash, canonical_json
from app.audit.merkle import build_merkle_proof, verify_merkle_proof
from app.audit.service import AuditLedgerService
from app.core.exceptions import LedgerIntegrityError
from app.models.audit_ledger import AuditLedgerEntry


def _make_entry(
    *,
    sequence_number: int,
    previous_hash: str | None,
    created_at: datetime,
    event_type: str = "governance.action_requested",
) -> AuditLedgerEntry:
    entry_hash = build_entry_hash(
        sequence_number=sequence_number,
        event_type=event_type,
        actor_type="system",
        actor_id="governance_engine",
        subject_type="action",
        subject_id=f"action-{sequence_number}",
        action_id=None,
        correlation_id=f"corr-{sequence_number}",
        payload={"step": sequence_number},
        previous_hash=previous_hash,
        created_at=created_at,
    )
    return AuditLedgerEntry(
        id=uuid.uuid4(),
        sequence_number=sequence_number,
        event_type=event_type,
        actor_type="system",
        actor_id="governance_engine",
        subject_type="action",
        subject_id=f"action-{sequence_number}",
        action_id=None,
        correlation_id=f"corr-{sequence_number}",
        payload={"step": sequence_number},
        previous_hash=previous_hash,
        entry_hash=entry_hash,
        merkle_leaf_hash=build_merkle_leaf_hash(entry_hash),
        created_at=created_at,
    )


def test_canonical_json_is_deterministic():
    first = canonical_json({"b": 2, "a": {"d": 4, "c": 3}})
    second = canonical_json({"a": {"c": 3, "d": 4}, "b": 2})
    assert first == second


def test_merkle_proof_round_trip():
    leaves = [build_merkle_leaf_hash(f"entry-{index}") for index in range(4)]
    merkle_root, proof = build_merkle_proof(leaves, 2)
    assert merkle_root is not None
    assert verify_merkle_proof(leaves[2], proof, merkle_root) is True
    assert verify_merkle_proof(leaves[1], proof, merkle_root) is False


@pytest.mark.asyncio
async def test_verify_ledger_detects_broken_hash_chain():
    created_at = datetime(2026, 6, 28, 12, 0, tzinfo=timezone.utc)
    entry_one = _make_entry(sequence_number=1, previous_hash=None, created_at=created_at)
    entry_two = _make_entry(
        sequence_number=2,
        previous_hash="tampered-previous-hash",
        created_at=created_at,
    )

    # Insert test entries into mock MongoDB directly
    await entry_one.insert()
    await entry_two.insert()

    with pytest.raises(LedgerIntegrityError):
        await AuditLedgerService.verify_ledger()


@pytest.mark.asyncio
async def test_append_entry_retries_after_integrity_conflict(monkeypatch):
    created_at = datetime(2026, 6, 28, 12, 30, tzinfo=timezone.utc)
    first_head = _make_entry(sequence_number=1, previous_hash=None, created_at=created_at)
    second_head = _make_entry(
        sequence_number=2,
        previous_hash=first_head.entry_hash,
        created_at=created_at,
    )

    find_calls = 0
    async def mock_first_or_none(*args, **kwargs):
        nonlocal find_calls
        find_calls += 1
        if find_calls == 1:
            return first_head
        return second_head

    # Mock Beanie query chain
    mock_query = MagicMock()
    mock_query.sort.return_value.first_or_none = mock_first_or_none
    monkeypatch.setattr(AuditLedgerEntry, "find_all", lambda *args, **kwargs: mock_query)

    insert_calls = 0
    async def mock_insert(self, *args, **kwargs):
        nonlocal insert_calls
        insert_calls += 1
        if insert_calls == 1:
            from pymongo.errors import DuplicateKeyError
            raise DuplicateKeyError("Duplicate key error simulated")
        return self

    monkeypatch.setattr(AuditLedgerEntry, "insert", mock_insert)
    monkeypatch.setattr("app.audit.service.utc_now", lambda: created_at)

    entry = await AuditLedgerService.append_entry(
        event_type="security.login_succeeded",
        actor_type="user",
        actor_id="admin",
        subject_type="session",
        subject_id="admin",
        payload={"role": "admin"},
    )

    assert entry.sequence_number == 3
    assert entry.previous_hash == second_head.entry_hash
    assert insert_calls == 2
