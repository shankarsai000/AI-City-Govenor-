"""
MongoDB connection and Beanie ODM initialization.
All database I/O is asynchronous and non-blocking.
"""
from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_client: AsyncIOMotorClient | None = None


async def init_database() -> None:
    """
    Initialize MongoDB connection and Beanie ODM document models.
    Called once during application startup.
    """
    global _client
    settings = get_settings()

    logger.info("Initializing MongoDB connection", uri=settings.MONGODB_URI.split("@")[-1])

    _client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = _client[settings.MONGODB_DB_NAME]

    # Import models here to prevent circular imports during init_beanie
    from app.models.agent import Agent
    from app.models.action import Action
    from app.models.policy import Policy
    from app.models.approval import Approval
    from app.models.city_state_snapshot import CityStateSnapshot
    from app.models.audit_ledger import AuditLedgerEntry
    from app.models.digital_twin import CityDigitalTwin
    from app.models.decision_graph import DecisionGraph
    from app.models.agent_memory import AgentMemory
    from app.models.embeddings import PolicyEmbedding, IncidentEmbedding, AuditEmbedding

    await init_beanie(
        database=db,
        document_models=[
            Agent,
            Action,
            Policy,
            Approval,
            CityStateSnapshot,
            AuditLedgerEntry,
            CityDigitalTwin,
            DecisionGraph,
            AgentMemory,
            PolicyEmbedding,
            IncidentEmbedding,
            AuditEmbedding,
        ],
    )
    logger.info("MongoDB connection and Beanie ODM initialized successfully")


async def close_database() -> None:
    """Gracefully close the MongoDB connection. Called on application shutdown."""
    global _client
    if _client:
        _client.close()
        _client = None
        logger.info("MongoDB connection closed")


def get_db():
    """
    Retrieve the raw Motor database instance.
    Usually Beanie Document models are used directly, but this is available if needed.
    """
    global _client
    if _client is None:
        raise RuntimeError("Database engine not initialized. Call init_database() first.")
    settings = get_settings()
    return _client[settings.MONGODB_DB_NAME]
