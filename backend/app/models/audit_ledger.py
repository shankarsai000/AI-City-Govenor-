import uuid
from datetime import datetime, timezone
from typing import Any
from beanie import Document
from pydantic import Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AuditLedgerEntry(Document):
    """Immutable cryptographic audit record for platform events."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    sequence_number: int
    event_type: str
    actor_type: str | None = None
    actor_id: str | None = None
    subject_type: str | None = None
    subject_id: str | None = None
    action_id: uuid.UUID | None = None
    correlation_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    previous_hash: str | None = None
    entry_hash: str
    merkle_leaf_hash: str
    created_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "audit_ledger_entries"
        indexes = [
            "sequence_number",
            "event_type",
            "action_id",
            "correlation_id",
            "created_at",
            "entry_hash",
        ]
