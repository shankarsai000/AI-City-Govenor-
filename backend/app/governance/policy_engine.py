from typing import Any
from app.core.exceptions import PolicyViolationError
from app.core.logging import get_logger
from app.models.policy import Policy

logger = get_logger(__name__)


class PolicyEngine:
    """
    Evaluates actions against policies defined in MongoDB.
    Policies govern boundaries like rate limits, threshold overrides,
    and conditional permissions.
    """

    @staticmethod
    async def evaluate(domain: str, action_type: str, payload: dict[str, Any], context: dict[str, Any]) -> str:
        """
        Evaluate domain policies.
        Returns:
            "allow" if all policies allow it
            "require_approval" if any policy elevates it
        Raises:
            PolicyViolationError if any policy explicitly denies it
        """
        # Retrieve active policies sorted by priority descending from MongoDB
        policies = await Policy.find(
            Policy.domain == domain,
            Policy.is_active == True
        ).sort(-Policy.priority).to_list()

        decision = "allow"

        for policy in policies:
            # Check if this policy applies to the requested action
            target_actions = policy.conditions.get("actions", [])
            if target_actions and action_type not in target_actions:
                continue

            # Evaluate rules
            if PolicyEngine._match_conditions(policy.conditions, payload, context):
                logger.info(
                    "Policy matched",
                    policy=policy.name,
                    rule_type=policy.rule_type,
                    action=action_type,
                )
                if policy.rule_type == "deny":
                    raise PolicyViolationError(
                        f"Action '{action_type}' denied by policy '{policy.name}'."
                    )
                elif policy.rule_type == "require_approval":
                    decision = "require_approval"

        return decision

    @staticmethod
    def _match_conditions(conditions: dict[str, Any], payload: dict[str, Any], context: dict[str, Any]) -> bool:
        """
        Matches standard condition keys:
        - payload_fields: matches exact values or bounds (e.g. gt, lt)
        - context_fields: matches active context (e.g. declared_emergency)
        """
        # 1. Check payload constraints
        payload_constraints = conditions.get("payload", {})
        for field, constraint in payload_constraints.items():
            val = payload.get(field)
            if isinstance(constraint, dict):
                if "gt" in constraint and (val is None or val <= constraint["gt"]):
                    return False
                if "lt" in constraint and (val is None or val >= constraint["lt"]):
                    return False
                if "eq" in constraint and val != constraint["eq"]:
                    return False
            elif val != constraint:
                return False

        # 2. Check context constraints
        context_constraints = conditions.get("context", {})
        for field, constraint in context_constraints.items():
            val = context.get(field)
            if val != constraint:
                return False

        return True
