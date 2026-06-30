"""
ArmorIQ Integration Exceptions.

Design: SDK errors are wrapped into our own typed exceptions so that
governance code never has a direct dependency on the SDK's internal
error hierarchy. If ArmorIQ changes its error types, only this file
needs updating.
"""


class ArmorIQError(Exception):
    """Base class for all ArmorIQ integration errors."""

    def __init__(self, message: str, *, code: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class ArmorIQUnavailableError(ArmorIQError):
    """ArmorIQ service is unreachable (network timeout, DNS failure, etc.)."""


class IntentCaptureFailed(ArmorIQError):
    """capture_plan() rejected the plan structure or MCP name is not registered."""


class TokenMintFailed(ArmorIQError):
    """get_intent_token() failed — plan invalid or policy denied token issuance."""


class ExecutionBlocked(ArmorIQError):
    """
    invoke() was blocked by the ArmorIQ proxy.

    This means the agent attempted an action that was not in its
    cryptographically signed intent plan. This is a security event.
    """


class DelegationFailed(ArmorIQError):
    """delegate() failed — parent token expired or insufficient privileges."""


class ArmorIQClientNotInitialized(ArmorIQError):
    """The ArmorIQ client singleton has not been initialized yet."""
