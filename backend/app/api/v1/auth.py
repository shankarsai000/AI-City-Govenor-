"""Authentication router — Stage 7 JWT, refresh, and logout flows."""
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.audit.service import AuditLedgerService
from app.config import OperatorAccountSettings, get_settings
from app.core.exceptions import AuthenticationError
from app.security.dependencies import get_current_principal, oauth2_scheme
from app.security.jwt_service import JWTService
from app.security.passwords import verify_password
from app.security.principals import AuthenticatedPrincipal
from app.security.rate_limiter import RateLimiter, build_bucket, get_client_ip
from app.security.token_store import is_token_revoked, revoke_token

router = APIRouter()


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime
    username: str
    role: str


class LogoutResponse(BaseModel):
    message: str


def _get_operator_account(username: str) -> OperatorAccountSettings:
    settings = get_settings()
    for account in settings.SECURITY_OPERATORS:
        if account.username == username:
            return account
    raise AuthenticationError("Invalid username or password.")


@router.post("/login")
async def login(payload: LoginRequest, request: Request) -> TokenResponse:
    settings = get_settings()
    client_ip = get_client_ip(request)
    bucket = build_bucket("login", f"{payload.username}:{client_ip}")
    await RateLimiter.enforce(bucket, settings.LOGIN_RATE_LIMIT, details={"ip": client_ip})

    account = _get_operator_account(payload.username)
    if account.disabled:
        raise AuthenticationError("Operator account is disabled.")

    if not verify_password(payload.password, account.password_hash):
        raise AuthenticationError("Invalid username or password.")

    access_token, access_expires_at = JWTService.create_access_token(account.username, account.role)
    refresh_token, refresh_expires_at = JWTService.create_refresh_token(account.username, account.role)
    await AuditLedgerService.append_entry(
        event_type="security.login_succeeded",
        actor_type="user",
        actor_id=account.username,
        subject_type="session",
        subject_id=account.username,
        payload={"role": account.role, "ip": client_ip},
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        access_token_expires_at=access_expires_at,
        refresh_token_expires_at=refresh_expires_at,
        username=account.username,
        role=account.role,
    )


@router.post("/refresh")
async def refresh(payload: RefreshRequest) -> TokenResponse:
    principal, expires_at = JWTService.decode_token(payload.refresh_token, expected_type="refresh")
    if await is_token_revoked(principal.token_id):
        raise AuthenticationError("Refresh token has been revoked.")

    account = _get_operator_account(principal.username)
    if account.disabled:
        raise AuthenticationError("Operator account is disabled.")

    await revoke_token(principal.token_id, expires_at)
    access_token, access_expires_at = JWTService.create_access_token(account.username, account.role)
    refresh_token, refresh_expires_at = JWTService.create_refresh_token(account.username, account.role)
    await AuditLedgerService.append_entry(
        event_type="security.token_refreshed",
        actor_type="user",
        actor_id=account.username,
        subject_type="session",
        subject_id=principal.token_id,
        payload={"role": account.role},
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        access_token_expires_at=access_expires_at,
        refresh_token_expires_at=refresh_expires_at,
        username=account.username,
        role=account.role,
    )


@router.post("/logout")
async def logout(token: str = Depends(oauth2_scheme)) -> LogoutResponse:
    principal, expires_at = JWTService.decode_token(token, expected_type="access")
    await revoke_token(principal.token_id, expires_at)
    await AuditLedgerService.append_entry(
        event_type="security.token_revoked",
        actor_type="user",
        actor_id=principal.username,
        subject_type="session",
        subject_id=principal.token_id,
        payload={"role": principal.role},
    )
    return LogoutResponse(message="Access token revoked successfully.")


@router.get("/me")
async def get_current_session(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> dict[str, str]:
    return {
        "username": principal.username,
        "role": principal.role,
        "subject": principal.subject,
    }
