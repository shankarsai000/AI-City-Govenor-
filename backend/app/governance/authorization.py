import json
from typing import Any
import uuid
from datetime import datetime, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from app.core.exceptions import AuthenticationError, AuthorizationError, ReplayAttackError
from app.core.logging import get_logger
from app.models.agent import Agent
from app.security.nonce_store import NonceStore

logger = get_logger(__name__)


def verify_signature(public_key_pem: str, signature_hex: str, payload: dict[str, Any]) -> bool:
    """Verify an agent's RSA signature over a JSON payload."""
    try:
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode("utf-8")
        )
        serialized = json.dumps(payload, sort_keys=True).encode("utf-8")
        
        # This will raise InvalidSignature if signature is invalid
        public_key.verify(
            bytes.fromhex(signature_hex),
            serialized,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return True
    except (InvalidSignature, Exception) as e:
        logger.warning("Signature verification failed", error=str(e))
        return False


async def check_agent(agent_id: str, action_req_payload: dict[str, Any], signature_hex: str) -> Agent:
    """
    Validate that:
    1. Agent exists in the registry (MongoDB).
    2. Agent is active (not suspended/error).
    3. Action signature is cryptographically valid.
    """
    agent = await Agent.get(uuid.UUID(agent_id))

    if not agent:
        raise AuthorizationError(f"Agent ID {agent_id} not registered.")

    if agent.status != "active":
        raise AuthorizationError(f"Agent {agent.name} is suspended (current status: {agent.status}).")

    # Verify signature first so a forged payload cannot reserve a nonce.
    if not verify_signature(agent.public_key, signature_hex, action_req_payload):
        raise AuthenticationError(f"Cryptographic signature check failed for agent {agent.name}.")

    nonce = action_req_payload.get("nonce")
    if not nonce:
        raise AuthenticationError("Missing nonce in signed action payload.")

    nonce_registered = await NonceStore.register(subject=f"agent:{agent_id}", nonce=nonce)
    if not nonce_registered:
        raise ReplayAttackError(f"Replay detected for nonce '{nonce}' from agent {agent.name}.")

    agent.last_seen_at = datetime.now(timezone.utc)
    await agent.save()

    return agent
