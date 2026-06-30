import uuid
from datetime import datetime, timezone
from typing import Any
from beanie import Document
from pydantic import BaseModel, Field


class PolicyNode(BaseModel):
    policy_id: uuid.UUID | None = None
    policy_name: str
    rule_type: str
    matched: bool = True
    details: dict[str, Any] = Field(default_factory=dict)


class RiskNode(BaseModel):
    risk_level: str
    requires_human: bool
    details: dict[str, Any] = Field(default_factory=dict)


class ArmorIQNode(BaseModel):
    plan_id: str | None = None
    status: str
    authorized: bool
    details: dict[str, Any] = Field(default_factory=dict)


class MLNode(BaseModel):
    is_anomalous: bool
    anomaly_score: float
    confidence: float
    top_features: list[dict[str, Any]] = Field(default_factory=list)


class HumanApprovalNode(BaseModel):
    approval_id: uuid.UUID
    decision: str
    reason: str | None = None
    approver: str | None = None
    decided_at: datetime | None = None


class ExecutionNode(BaseModel):
    status: str
    result: dict[str, Any] = Field(default_factory=dict)
    executed_at: datetime | None = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DecisionGraph(Document):
    """
    Explainable governance: stores the entire decision pipeline trace for one action.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    action_id: uuid.UUID
    agent_id: uuid.UUID
    agent_name: str
    domain: str
    action_type: str

    policies_applied: list[PolicyNode] = Field(default_factory=list)
    risk_assessment: RiskNode
    armoriq_decision: ArmorIQNode
    ml_assessment: MLNode | None = None
    human_approval: HumanApprovalNode | None = None
    execution_result: ExecutionNode | None = None
    audit_entry_id: uuid.UUID | None = None
    created_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "decision_graphs"
        indexes = [
            "action_id",
            "agent_id",
            "created_at",
        ]
