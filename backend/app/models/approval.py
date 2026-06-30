import uuid
from datetime import datetime, timezone
from beanie import Document
from pydantic import Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Approval(Document):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    action_id: uuid.UUID
    approver_id: uuid.UUID | None = None  # Null if auto-approved or pending
    decision: str = "pending"  # 'pending', 'approved', 'rejected'
    reason: str | None = None
    approved_at: datetime | None = None

    class Settings:
        name = "approvals"
        indexes = [
            "action_id",
            "decision",
        ]
