import uuid
from datetime import datetime, timezone
from typing import Any
from beanie import Document
from pydantic import Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Action(Document):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    agent_id: uuid.UUID
    action_type: str  # 'reroute_traffic', etc.
    payload: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"  # 'pending', 'approved', 'rejected', 'executed', 'failed'
    risk_level: str  # 'low', 'medium', 'high', 'critical'
    requires_human: bool = False
    plan_id: str | None = None  # ArmorIQ plan reference
    signature: str  # RSA signature of payload
    nonce: str  # Replay protection
    requested_at: datetime = Field(default_factory=utc_now)
    approved_at: datetime | None = None
    executed_at: datetime | None = None

    class Settings:
        name = "actions"
        indexes = [
            "agent_id",
            "status",
            "requested_at",
        ]
