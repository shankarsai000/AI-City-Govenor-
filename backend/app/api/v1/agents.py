from fastapi import APIRouter, Depends

from app.models.agent import Agent
from app.security.dependencies import require_roles
from app.security.principals import AuthenticatedPrincipal

router = APIRouter()


@router.get("/")
async def list_agents(
    principal: AuthenticatedPrincipal = Depends(require_roles("admin", "operator", "auditor")),
) -> dict[str, object]:
    """Retrieve all registered agents from the MongoDB registry."""
    agents = await Agent.find_all().sort(+Agent.name).to_list()
    return {
        "requested_by": principal.username,
        "count": len(agents),
        "results": [
            {
                "agent_id": str(agent.id),
                "name": agent.name,
                "domain": agent.domain,
                "status": agent.status,
                "capabilities": agent.capabilities,
                "last_seen_at": agent.last_seen_at.isoformat(),
            }
            for agent in agents
        ],
    }
