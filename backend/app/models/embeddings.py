import uuid
from beanie import Document
from pydantic import Field


class PolicyEmbedding(Document):
    """Semantic mapping for policy search."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    policy_id: uuid.UUID
    text: str
    embedding: list[float] | None = None

    class Settings:
        name = "policy_embeddings"


class IncidentEmbedding(Document):
    """Semantic mapping for incident clustering/retrieval."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    incident_id: str
    text: str
    embedding: list[float] | None = None

    class Settings:
        name = "incident_embeddings"


class AuditEmbedding(Document):
    """Semantic mapping for audit search and anomaly categorization."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    audit_entry_id: uuid.UUID
    text: str
    embedding: list[float] | None = None

    class Settings:
        name = "audit_embeddings"
