import uuid
from datetime import datetime, timezone
from typing import Any
from beanie import Document
from pydantic import Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CityStateSnapshot(Document):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    domain: str  # 'traffic', 'power', etc.
    state_data: dict[str, Any] = Field(default_factory=dict)
    version: int = 0
    triggered_by: str  # action_type
    action_id: uuid.UUID | None = None
    created_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "city_state_snapshots"
        indexes = [
            "domain",
            "version",
            "created_at",
        ]
