import abc
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.core.event_bus import publish_event
from app.core.logging import get_logger
from app.models.agent import Agent

logger = get_logger(__name__)


class BaseAgent(abc.ABC):
    """
    Abstract Base Agent class defining the multi-agent contract.
    Each domain agent (Traffic, Power, Water, Emergency) extends this class.
    """

    def __init__(self, name: str, domain: str) -> None:
        self.name = name
        self.domain = domain
        self.status = "idle"
        self._private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        self._public_key = self._private_key.public_key()
        self.db_id: uuid.UUID | None = None

    @abc.abstractmethod
    def get_capabilities(self) -> list[dict[str, Any]]:
        """
        Return the capability matrix for this agent.
        Format:
        [
            {
                "action": "action_name",
                "risk": "low/medium/high/critical",
                "requires_human": True/False,
                "rate_limit": "10/minute"
            }
        ]
        """
        pass

    def get_public_key_pem(self) -> str:
        """Get the RSA public key in PEM format."""
        pem = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return pem.decode("utf-8")

    def sign_payload(self, payload: dict[str, Any]) -> str:
        """Sign a dictionary payload with the agent's private key."""
        serialized = json.dumps(payload, sort_keys=True).encode("utf-8")
        signature = self._private_key.sign(
            serialized,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return signature.hex()

    async def register(self) -> uuid.UUID:
        """Register or update agent status and capabilities in the MongoDB registry."""
        db_agent = await Agent.find_one({"name": self.name})

        if db_agent:
            db_agent.status = "active"
            db_agent.capabilities = self.get_capabilities()
            db_agent.public_key = self.get_public_key_pem()
            db_agent.last_seen_at = datetime.now(timezone.utc)
            await db_agent.save()
            self.db_id = db_agent.id
            logger.info("Agent re-registered", name=self.name, id=self.db_id)
        else:
            db_agent = Agent(
                id=uuid.uuid4(),
                name=self.name,
                domain=self.domain,
                status="active",
                public_key=self.get_public_key_pem(),
                capabilities=self.get_capabilities(),
                last_seen_at=datetime.now(timezone.utc),
            )
            await db_agent.insert()
            self.db_id = db_agent.id
            logger.info("New agent registered", name=self.name, id=self.db_id)

        self.status = "active"
        return self.db_id

    async def start(self) -> None:
        """Startup lifecycle: registers agent and joins the event loop."""
        await self.register()
        logger.info("Agent active, starting subscription task", name=self.name)

    async def request_action(
        self, action_type: str, payload: dict[str, Any], correlation_id: str | None = None
    ) -> None:
        """
        Request a governance action. The action payload is signed by the agent
        and sent to the governance engine for validation.
        """
        nonce = uuid.uuid4().hex
        action_req = {
            "agent_name": self.name,
            "action_type": action_type,
            "payload": payload,
            "nonce": nonce,
        }
        signature = self.sign_payload(action_req)

        event_payload = {
            "agent_id": str(self.db_id),
            "action_type": action_type,
            "payload": payload,
            "nonce": nonce,
            "signature": signature,
        }

        # Send action request to the governance entry point via the event bus
        await publish_event(
            event_type="governance.action_requested",
            source_agent=self.name,
            payload=event_payload,
            correlation_id=correlation_id,
        )
        logger.info("Action requested", agent=self.name, action_type=action_type)

    async def store_memory(
        self,
        memory_type: str,
        content: str,
        importance: float = 0.5,
        metadata_fields: dict[str, Any] | None = None,
    ) -> None:
        """Stores a significant event/action in the agent's memory collection for future RAG support."""
        if not self.db_id:
            logger.warning("Cannot store agent memory before registration", name=self.name)
            return

        from app.models.agent_memory import AgentMemory

        memory = AgentMemory(
            id=uuid.uuid4(),
            agent_id=self.db_id,
            agent_name=self.name,
            memory_type=memory_type,
            content=content,
            importance=importance,
            metadata_fields=metadata_fields or {},
        )
        await memory.insert()
        logger.debug("Stored agent memory record", name=self.name, type=memory_type)
