import uuid
from datetime import datetime, timezone
from typing import Any
from beanie import Document
from pydantic import Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Policy(Document):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    domain: str  # 'traffic', 'power', etc.
    rule_type: str  # 'allow', 'deny', 'require_approval', 'rate_limit'
    conditions: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0
    is_active: bool = True
    created_by: uuid.UUID | None = None
    created_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "policies"
        indexes = [
            "name",
            "domain",
            "is_active",
        ]
