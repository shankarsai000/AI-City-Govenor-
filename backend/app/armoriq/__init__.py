"""
ArmorIQ integration package.

Public API surface exposed to the rest of the application.
"""
from app.armoriq.client import initialize_client, shutdown_client, is_enabled
from app.armoriq.intent_service import IntentService, IntentContext
from app.armoriq.plan_builder import build_plan, build_prompt
from app.armoriq.exceptions import (
    ArmorIQError,
    ArmorIQUnavailableError,
    IntentCaptureFailed,
    TokenMintFailed,
    ExecutionBlocked,
    DelegationFailed,
    ArmorIQClientNotInitialized,
)
