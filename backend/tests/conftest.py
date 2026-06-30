import os
import sys
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from mongomock_motor import AsyncMongoMockClient

# Ensure backend root is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set test environment variables before any imports
os.environ["APP_ENV"] = "test"
os.environ["MONGODB_URI"] = "mongodb://localhost:27017/test_db"
os.environ["MONGODB_DB_NAME"] = "test_db"
os.environ["REDIS_URL"] = "redis://localhost:6379/9"
os.environ["DEBUG"] = "false"


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    """Override settings for tests."""
    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "APP_ENV", "test")
    return settings


@pytest.fixture(autouse=True)
def init_mock_db(monkeypatch):
    """Initialize Beanie synchronously using the active event loop."""
    from beanie import init_beanie
    
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

    client = AsyncMongoMockClient()
    db = client["test_db"]

    async def _init():
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

    # Run the async init using the event loop
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_init())

    # Patch get_db in app.core.database to return mock db
    monkeypatch.setattr("app.core.database.get_db", lambda: db)

    yield db


@pytest.fixture
def mock_db_session():
    """Dummy fixture for tests expecting it as an argument."""
    mock = AsyncMock()
    mock.execute = MagicMock()
    return mock


@pytest.fixture(autouse=True)
def mock_publish_event(monkeypatch):
    """Mock publish_event globally across all modules."""
    publish_mock = AsyncMock(return_value="mock_event_id")

    targets = [
        "app.core.event_bus.publish_event",
        "app.agents.base_agent.publish_event",
        "app.governance.approval_pipeline.publish_event",
        "app.governance.engine.publish_event",
    ]
    for target in targets:
        monkeypatch.setattr(target, publish_mock)

    return publish_mock
