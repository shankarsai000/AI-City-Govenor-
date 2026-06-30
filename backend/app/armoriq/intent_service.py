"""
ArmorIQ Intent Service.

This is the primary integration point between our GovernanceEngine and ArmorIQ.
It orchestrates the full 3-step ArmorIQ intent enforcement flow:

    Step 1: capture_plan()      → registers the agent's declared intent
    Step 2: get_intent_token()  → mints a cryptographic proof of that intent
    Step 3: invoke()            → executes through ArmorIQ's enforcing proxy
             └→ Any tool call NOT in the declared plan is BLOCKED here.

Design decisions:
- The ArmorIQ Python SDK is synchronous (httpx sync). We use asyncio.to_thread()
  to run SDK calls on a thread pool, keeping our async event loop unblocked.
- When ArmorIQ is not configured (no API key in dev), all methods succeed as
  no-ops. This is logged clearly so developers know enforcement is disabled.
- SDK exceptions are caught and re-raised as our own typed exceptions
  (ArmorIQError subclasses) to keep the caller decoupled from SDK internals.
"""
import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from app.armoriq import client as armoriq_client
from app.armoriq.exceptions import (
    ArmorIQUnavailableError,
    DelegationFailed,
    ExecutionBlocked,
    IntentCaptureFailed,
    TokenMintFailed,
)
from app.armoriq.plan_builder import build_plan, build_prompt
from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class IntentContext:
    """
    Holds the ArmorIQ intent artifacts for a single governance action.

    This is returned after prepare_action() and passed to execute_action().
    Stored on the Action model for full audit traceability.
    """

    plan_capture_id: str
    """Unique ID of the captured plan from ArmorIQ (PlanCapture.id)."""

    intent_token_id: str
    """Unique ID of the intent token (IntentToken.id). Used for audit linking."""

    intent_token: Any
    """The raw IntentToken object — required for invoke() and delegate()."""

    mcp_name: str
    """The MCP server name this action will be executed against."""

    tool_name: str
    """The specific tool within the MCP."""

    armoriq_enabled: bool = True
    """False when ArmorIQ is not configured (no API key)."""


class IntentService:
    """
    Orchestrates ArmorIQ intent enforcement for a single agent action.

    Lifecycle: instantiate once per action request; do not share across requests.
    """

    def __init__(self, user_email: str | None = None):
        settings = get_settings()
        self._user_email = user_email or settings.ARMORIQ_USER_EMAIL
        self._enabled = armoriq_client.is_enabled()

    async def prepare_action(
        self,
        agent_id: str,
        agent_type: str,
        action_type: str,
        params: dict[str, Any] | None = None,
        risk_level: str = "medium",
    ) -> IntentContext:
        """
        Execute Steps 1 and 2: capture plan + mint intent token.

        Args:
            agent_id: UUID of the agent making the request.
            agent_type: e.g. "traffic_agent"
            action_type: e.g. "adjust_signal_timing"
            params: Action parameters.
            risk_level: "low" | "medium" | "high" | "critical"

        Returns:
            IntentContext with plan_capture_id, intent_token_id, and the
            IntentToken object needed for execute_action().
        """
        if not self._enabled:
            logger.warning(
                "ArmorIQ is DISABLED. Action %s by agent %s proceeds without "
                "external intent enforcement.",
                action_type,
                agent_id,
            )
            return IntentContext(
                plan_capture_id="disabled",
                intent_token_id="disabled",
                intent_token=None,
                mcp_name="disabled",
                tool_name="disabled",
                armoriq_enabled=False,
            )

        plan = build_plan(agent_type, action_type, params, risk_level)
        prompt = build_prompt(agent_type, action_type, params)
        mcp_name = plan["steps"][0]["mcp"]
        tool_name = plan["steps"][0]["action"]

        # ── Step 1: Capture Plan ──────────────────────────────────────────────
        plan_capture = await self._capture_plan(
            llm="city-governor-v1",
            prompt=prompt,
            plan=plan,
            metadata={
                "agent_id": agent_id,
                "agent_type": agent_type,
                "action_type": action_type,
                "risk_level": risk_level,
            },
        )

        # ── Step 2: Mint Intent Token ─────────────────────────────────────────
        # Policy: allow all actions by default; deny overrides come from
        # ArmorIQ platform policies configured per agent type.
        policy = {
            "allow": [f"{mcp_name}:{tool_name}"],
            "deny": [],
        }
        intent_token = await self._get_intent_token(
            plan_capture=plan_capture,
            policy=policy,
            validity_seconds=300.0,  # 5-minute window for execution
        )

        logger.info(
            "Intent token minted: plan_id=%s token_id=%s agent=%s action=%s",
            plan_capture.id,
            intent_token.id,
            agent_id,
            action_type,
        )

        return IntentContext(
            plan_capture_id=plan_capture.id,
            intent_token_id=intent_token.id,
            intent_token=intent_token,
            mcp_name=mcp_name,
            tool_name=tool_name,
            armoriq_enabled=True,
        )

    async def execute_action(
        self,
        intent_ctx: IntentContext,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute Step 3: invoke the action through ArmorIQ's enforcing proxy.

        The proxy cryptographically verifies that this specific (mcp, action)
        pair was declared in the intent token. If not, execution is BLOCKED.

        Args:
            intent_ctx: The IntentContext from prepare_action().
            params: Actual parameters for the action (may differ from plan hints).

        Returns:
            MCPResult data as a dict.

        Raises:
            ExecutionBlocked: If the proxy denies the action.
        """
        if not intent_ctx.armoriq_enabled:
            logger.warning(
                "ArmorIQ DISABLED — simulating successful execution of %s:%s",
                intent_ctx.mcp_name,
                intent_ctx.tool_name,
            )
            return {"status": "executed", "armoriq_enforced": False, "params": params}

        result = await self._invoke(
            mcp=intent_ctx.mcp_name,
            action=intent_ctx.tool_name,
            intent_token=intent_ctx.intent_token,
            params=params,
            user_email=self._user_email,
        )

        logger.info(
            "Action executed via ArmorIQ proxy: mcp=%s action=%s token_id=%s",
            intent_ctx.mcp_name,
            intent_ctx.tool_name,
            intent_ctx.intent_token_id,
        )
        return result

    async def delegate_to_agent(
        self,
        intent_ctx: IntentContext,
        delegate_agent_public_key: str,
        delegate_agent_id: str,
        subtask: str | None = None,
        allowed_actions: list[str] | None = None,
    ) -> Any:
        """
        Delegate a constrained subset of the intent token's authority to another agent.

        Used when the Emergency agent needs to sub-delegate traffic control to
        the Traffic agent. The delegate token has strict action constraints and
        a shorter validity window.

        Args:
            intent_ctx: The parent IntentContext from prepare_action().
            delegate_agent_public_key: RSA public key PEM of the delegate agent.
            delegate_agent_id: ID of the delegate agent (for logging).
            subtask: Human-readable description of the subtask.
            allowed_actions: List of "<mcp>:<action>" pairs the delegate may call.
                             Defaults to the single action in the parent context.

        Returns:
            The delegate IntentToken.
        """
        if not intent_ctx.armoriq_enabled:
            logger.warning(
                "ArmorIQ DISABLED — delegation to agent %s skipped.", delegate_agent_id
            )
            return None

        if allowed_actions is None:
            allowed_actions = [f"{intent_ctx.mcp_name}:{intent_ctx.tool_name}"]

        delegate_token = await self._delegate(
            intent_token=intent_ctx.intent_token,
            delegate_public_key=delegate_agent_public_key,
            validity_seconds=120.0,  # 2-minute window for delegate
            allowed_actions=allowed_actions,
            target_agent=delegate_agent_id,
            subtask=subtask or f"Delegated: {intent_ctx.tool_name}",
        )

        logger.info(
            "Intent delegated: parent_token=%s → delegate_agent=%s allowed=%s",
            intent_ctx.intent_token_id,
            delegate_agent_id,
            allowed_actions,
        )
        return delegate_token

    # ── Private SDK wrappers ──────────────────────────────────────────────────
    # Each wraps a synchronous SDK call in asyncio.to_thread() and maps SDK
    # exceptions to our typed exceptions.

    async def _capture_plan(self, llm: str, prompt: str, plan: dict, metadata: dict) -> Any:
        """Async wrapper for client.capture_plan()."""
        try:
            client = armoriq_client.get_client()
            scoped = client.for_user(self._user_email)
            return await asyncio.to_thread(
                scoped.capture_plan,
                llm=llm,
                prompt=prompt,
                plan=plan,
                metadata=metadata,
            )
        except Exception as exc:
            raise IntentCaptureFailed(
                f"ArmorIQ capture_plan() failed: {exc}",
                details={"plan": plan, "error": str(exc)},
            ) from exc

    async def _get_intent_token(
        self,
        plan_capture: Any,
        policy: dict | None = None,
        validity_seconds: float = 300.0,
    ) -> Any:
        """Async wrapper for client.get_intent_token()."""
        try:
            client = armoriq_client.get_client()
            scoped = client.for_user(self._user_email)
            return await asyncio.to_thread(
                scoped.get_intent_token,
                plan_capture=plan_capture,
                policy=policy,
                validity_seconds=validity_seconds,
            )
        except Exception as exc:
            raise TokenMintFailed(
                f"ArmorIQ get_intent_token() failed: {exc}",
                details={"error": str(exc)},
            ) from exc

    async def _invoke(
        self,
        mcp: str,
        action: str,
        intent_token: Any,
        params: dict | None = None,
        user_email: str | None = None,
    ) -> dict:
        """Async wrapper for client.invoke()."""
        try:
            client = armoriq_client.get_client()
            scoped = client.for_user(self._user_email)
            result = await asyncio.to_thread(
                scoped.invoke,
                mcp=mcp,
                action=action,
                intent_token=intent_token,
                params=params,
                user_email=user_email,
            )
            # MCPResult → dict
            if isinstance(result, dict):
                return result
            if hasattr(result, "model_dump"):
                return result.model_dump()
            if hasattr(result, "__dict__"):
                return vars(result)
            return {"result": result}
        except Exception as exc:
            error_str = str(exc).lower()
            if "blocked" in error_str or "denied" in error_str or "forbidden" in error_str:
                raise ExecutionBlocked(
                    f"ArmorIQ proxy BLOCKED execution of {mcp}:{action}: {exc}",
                    code="PROXY_BLOCKED",
                    details={"mcp": mcp, "action": action, "error": str(exc)},
                ) from exc
            raise ArmorIQUnavailableError(
                f"ArmorIQ invoke() failed: {exc}",
                details={"mcp": mcp, "action": action, "error": str(exc)},
            ) from exc

    async def _delegate(
        self,
        intent_token: Any,
        delegate_public_key: str,
        validity_seconds: float,
        allowed_actions: list[str],
        target_agent: str,
        subtask: str,
    ) -> Any:
        """Async wrapper for client.delegate()."""
        try:
            client = armoriq_client.get_client()
            scoped = client.for_user(self._user_email)
            return await asyncio.to_thread(
                scoped.delegate,
                intent_token=intent_token,
                delegate_public_key=delegate_public_key,
                validity_seconds=validity_seconds,
                allowed_actions=allowed_actions,
                target_agent=target_agent,
                subtask=subtask,
            )
        except Exception as exc:
            raise DelegationFailed(
                f"ArmorIQ delegate() failed: {exc}",
                details={"target_agent": target_agent, "error": str(exc)},
            ) from exc
