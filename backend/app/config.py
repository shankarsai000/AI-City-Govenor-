"""
Application configuration using pydantic-settings.

Design decision: All config comes from environment variables only — no config files
with secrets. pydantic-settings validates types at startup, so misconfiguration
fails fast before any service connects.
"""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OperatorAccountSettings(BaseModel):
    """Environment-backed operator account used for Stage 7 JWT auth."""

    username: str
    password_hash: str
    role: Literal["admin", "operator", "auditor"]
    disabled: bool = False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    APP_NAME: str = "AI City Governor"
    APP_VERSION: str = "1.0.0"
    APP_ENV: Literal["development", "staging", "production", "test"] = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False

    # ── Database (MongoDB) ────────────────────────────────────────────────────
    MONGODB_URI: str = "mongodb://city_gov:city_gov_pass@localhost:27017/city_governor?replicaSet=rs0"
    MONGODB_DB_NAME: str = "city_governor"

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 50

    # ── JWT & Cryptography ────────────────────────────────────────────────────
    JWT_ALGORITHM: str = "RS256"
    JWT_ISSUER: str = "ai-city-governor"
    JWT_AUDIENCE: str = "city-ops"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    RSA_PRIVATE_KEY_PATH: Path = Path(__file__).resolve().parent.parent / "keys" / "private.pem"
    RSA_PUBLIC_KEY_PATH: Path = Path(__file__).resolve().parent.parent / "keys" / "public.pem"
    SECURITY_OPERATORS: list[OperatorAccountSettings] = Field(default_factory=list)
    LOGIN_RATE_LIMIT: str = "5/minute"
    OPERATOR_RATE_LIMIT: str = "60/minute"

    # ── ArmorIQ ───────────────────────────────────────────────────────────────
    ARMORIQ_API_KEY: str = ""
    ARMORIQ_BASE_URL: str = "https://api.armoriq.io"
    ARMORIQ_TIMEOUT_SECONDS: int = 10
    # User email for ArmorIQ audit trail scoping (identifies this deployment)
    ARMORIQ_USER_EMAIL: str = "city-governor@infrastructure.gov"

    # ── Governance ────────────────────────────────────────────────────────────
    # Actions with risk >= this threshold require human approval
    HUMAN_APPROVAL_RISK_THRESHOLD: str = "high"
    # Nonce TTL in seconds (replay attack window)
    NONCE_TTL_SECONDS: int = 300
    # Max pending approvals before new actions are queued
    MAX_PENDING_APPROVALS: int = 100

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # ── Simulator ─────────────────────────────────────────────────────────────
    SIMULATOR_OUTPUT_DIR: Path = Path(__file__).resolve().parent.parent / "data" / "simulator"
    SIMULATOR_DEFAULT_LOG_COUNT: int = 2500
    SIMULATOR_DEFAULT_SEED: int = 2026
    SIMULATOR_DEFAULT_ANOMALY_RATE: float = 0.03

    # Machine Learning
    ML_MODEL_DIR: Path = Path(__file__).resolve().parent.parent / "data" / "ml"
    ML_ANOMALY_ESCALATION_ENABLED: bool = True
    ML_ANOMALY_MIN_CONFIDENCE: float = 0.55

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def rsa_private_key(self) -> str:
        """Read RSA private key from file — never stored in memory at module load."""
        return self.RSA_PRIVATE_KEY_PATH.read_text()

    @property
    def rsa_public_key(self) -> str:
        """Read RSA public key from file."""
        return self.RSA_PUBLIC_KEY_PATH.read_text()


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings singleton. Use this everywhere via FastAPI dependency
    injection rather than importing settings directly, enabling test overrides.
    """
    return Settings()
