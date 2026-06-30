import uuid
from datetime import datetime, timezone
from typing import Any, Literal
from beanie import Document
from pydantic import Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentMemory(Document):
    """
    Agent episodic memory document for future RAG capability.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    agent_id: uuid.UUID
    agent_name: str
    memory_type: Literal["incident", "approval", "failure", "observation"]
    content: str
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    embedding: list[float] | None = None
    metadata_fields: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "agent_memory"
        indexes = [
            "agent_id",
            "created_at",
            "memory_type",
        ]
