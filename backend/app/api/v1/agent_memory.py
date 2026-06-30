import uuid
from typing import Any
from fastapi import APIRouter, Depends, Query, HTTPException

from app.models.agent_memory import AgentMemory
from app.security.dependencies import require_roles
from app.security.principals import AuthenticatedPrincipal

router = APIRouter()


@router.get("/agents/{agent_id}/memory")
async def get_agent_memories(
    agent_id: uuid.UUID,
    limit: int = Query(default=30, ge=1, le=100),
    memory_type: str | None = Query(default=None),
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "operator", "auditor")),
) -> dict[str, Any]:
    """Retrieve episodic memories recorded by a specific agent for future RAG overlays."""
    query: dict[str, Any] = {"agent_id": agent_id}
    if memory_type:
        query["memory_type"] = memory_type

    memories = await AgentMemory.find(query).sort(-AgentMemory.created_at).limit(limit).to_list()
    return {
        "requested_by": principal.username,
        "agent_id": str(agent_id),
        "count": len(memories),
        "results": [m.model_dump(mode="json") for m in memories],
    }
