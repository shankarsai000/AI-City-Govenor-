from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any


def canonical_json(value: Any) -> str:
    """Serialize values deterministically for cryptographic hashing."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=_json_default)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def build_entry_hash_components(
    *,
    sequence_number: int,
    event_type: str,
    actor_type: str | None,
    actor_id: str | None,
    subject_type: str | None,
    subject_id: str | None,
    action_id: str | None,
    correlation_id: str | None,
    payload: dict[str, Any],
    previous_hash: str | None,
    created_at: datetime,
) -> dict[str, Any]:
    return {
        "sequence_number": sequence_number,
        "event_type": event_type,
        "actor_type": actor_type,
        "actor_id": actor_id,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "action_id": action_id,
        "correlation_id": correlation_id,
        "payload": payload,
        "previous_hash": previous_hash,
        "created_at": created_at.isoformat(),
    }


def build_entry_hash(**kwargs: Any) -> str:
    return sha256_hex(canonical_json(build_entry_hash_components(**kwargs)))


def build_merkle_leaf_hash(entry_hash: str) -> str:
    return sha256_hex(canonical_json({"entry_hash": entry_hash}))
