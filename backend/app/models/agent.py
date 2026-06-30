import uuid
from datetime import datetime, timezone
from typing import Any
from beanie import Document
from pydantic import Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Agent(Document):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    domain: str  # 'traffic', 'power', etc.
    status: str = "idle"  # 'idle', 'active', 'suspended', 'error'
    public_key: str  # RSA public key for verification
    capabilities: list[dict[str, Any]] = Field(default_factory=list)
    metadata_fields: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    last_seen_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "agents"
        indexes = [
            "name",
        ]
