"""
Custom exception hierarchy for AI City Governor.

Design decision: A rich exception hierarchy means:
1. Different error types map to different HTTP status codes automatically
2. Error handlers can distinguish governance failures from infra failures
3. Structured error responses carry machine-readable error codes
"""
from typing import Any


class CityGovernorError(Exception):
    """Base exception for all application errors."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


# ── Authentication & Authorization ────────────────────────────────────────────

class AuthenticationError(CityGovernorError):
    status_code = 401
    error_code = "AUTHENTICATION_FAILED"


class AuthorizationError(CityGovernorError):
    status_code = 403
    error_code = "AUTHORIZATION_DENIED"


class TokenExpiredError(AuthenticationError):
    error_code = "TOKEN_EXPIRED"


class InvalidTokenError(AuthenticationError):
    error_code = "INVALID_TOKEN"


# ── Governance ────────────────────────────────────────────────────────────────

class GovernanceError(CityGovernorError):
    status_code = 422
    error_code = "GOVERNANCE_VIOLATION"


class PolicyViolationError(GovernanceError):
    error_code = "POLICY_VIOLATION"


class CapabilityDeniedError(GovernanceError):
    status_code = 403
    error_code = "CAPABILITY_DENIED"


class ActionValidationError(GovernanceError):
    error_code = "ACTION_VALIDATION_FAILED"


class ApprovalRequiredError(GovernanceError):
    status_code = 202
    error_code = "APPROVAL_REQUIRED"


class ApprovalRejectedError(GovernanceError):
    status_code = 403
    error_code = "APPROVAL_REJECTED"


class ReplayAttackError(GovernanceError):
    status_code = 409
    error_code = "REPLAY_ATTACK_DETECTED"


class RateLimitExceededError(GovernanceError):
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"


# ── Agent ─────────────────────────────────────────────────────────────────────

class AgentError(CityGovernorError):
    status_code = 500
    error_code = "AGENT_ERROR"


class AgentNotFoundError(AgentError):
    status_code = 404
    error_code = "AGENT_NOT_FOUND"


class AgentSuspendedError(AgentError):
    status_code = 403
    error_code = "AGENT_SUSPENDED"


class AgentCommunicationError(AgentError):
    error_code = "AGENT_COMMUNICATION_ERROR"


# ── City State ────────────────────────────────────────────────────────────────

class CityStateError(CityGovernorError):
    error_code = "CITY_STATE_ERROR"


class ResourceLockError(CityStateError):
    status_code = 409
    error_code = "RESOURCE_LOCKED"


class ConflictDetectedError(CityStateError):
    status_code = 409
    error_code = "STATE_CONFLICT_DETECTED"


# ── Audit ─────────────────────────────────────────────────────────────────────

class AuditError(CityGovernorError):
    error_code = "AUDIT_ERROR"


class LedgerIntegrityError(AuditError):
    error_code = "LEDGER_INTEGRITY_VIOLATION"


# ── ArmorIQ ───────────────────────────────────────────────────────────────────

class ArmorIQError(CityGovernorError):
    error_code = "ARMORIQ_ERROR"


class ArmorIQAuthError(ArmorIQError):
    status_code = 401
    error_code = "ARMORIQ_AUTH_FAILED"


# Machine Learning

class MLError(CityGovernorError):
    error_code = "ML_ERROR"


class MLModelNotReadyError(MLError):
    status_code = 503
    error_code = "ML_MODEL_NOT_READY"


class MLDatasetError(MLError):
    status_code = 422
    error_code = "ML_DATASET_INVALID"


# ── Infrastructure ────────────────────────────────────────────────────────────

class DatabaseError(CityGovernorError):
    error_code = "DATABASE_ERROR"


class CacheError(CityGovernorError):
    error_code = "CACHE_ERROR"


class NotFoundError(CityGovernorError):
    status_code = 404
    error_code = "NOT_FOUND"
