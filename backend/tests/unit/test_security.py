import uuid
from unittest.mock import MagicMock

import pytest
from starlette.requests import Request

from app.agents import TrafficAgent
from app.api.v1.auth import LoginRequest, RefreshRequest, login, logout, refresh
from app.config import OperatorAccountSettings, get_settings
from app.core.exceptions import AuthenticationError, AuthorizationError, RateLimitExceededError, ReplayAttackError
from app.governance.authorization import check_agent
from app.models.agent import Agent
from app.security.dependencies import require_roles
from app.security.jwt_service import JWTService
from app.security.nonce_store import NonceStore
from app.security.passwords import hash_password, verify_password
from app.security.principals import AuthenticatedPrincipal
from app.security.rate_limiter import RateLimiter, build_bucket
from app.security.token_store import is_token_revoked


def _request_with_ip(ip_address: str) -> Request:
    scope = {
        "type": "http",
        "headers": [],
        "client": (ip_address, 12345),
        "method": "POST",
        "path": "/api/v1/auth/login",
    }
    return Request(scope)


def test_password_hash_round_trip():
    password = "AdminPass!234"
    password_hash = hash_password(password)
    assert verify_password(password, password_hash) is True
    assert verify_password("WrongPass!234", password_hash) is False


@pytest.mark.asyncio
async def test_require_roles_allows_expected_role():
    principal = AuthenticatedPrincipal(
        username="auditor",
        role="auditor",
        token_id="token-1",
        token_type="access",
    )
    dependency = require_roles("admin", "auditor")
    result = await dependency(principal=principal)
    assert result == principal


@pytest.mark.asyncio
async def test_rbac_dependency_rejects_invalid_role():
    principal = AuthenticatedPrincipal(
        username="operator",
        role="operator",
        token_id="token-1",
        token_type="access",
    )
    dependency = require_roles("admin")
    with pytest.raises(AuthorizationError):
        await dependency(principal=principal)


@pytest.mark.asyncio
async def test_nonce_store_blocks_replay():
    assert await NonceStore.register("agent:test", "nonce-1") is True
    assert await NonceStore.register("agent:test", "nonce-1") is False


@pytest.mark.asyncio
async def test_rate_limiter_enforces_limit():
    bucket = build_bucket("test", "security")
    await RateLimiter.enforce(bucket, "2/minute")
    await RateLimiter.enforce(bucket, "2/minute")
    with pytest.raises(RateLimitExceededError):
        await RateLimiter.enforce(bucket, "2/minute")


def test_jwt_issue_and_decode():
    access_token, access_expires_at = JWTService.create_access_token("admin", "admin")
    principal, decoded_expires_at = JWTService.decode_token(access_token, expected_type="access")
    assert principal.username == "admin"
    assert principal.role == "admin"
    assert int(decoded_expires_at.timestamp()) == int(access_expires_at.timestamp())


@pytest.mark.asyncio
async def test_auth_login_refresh_and_logout():
    settings = get_settings()
    settings.SECURITY_OPERATORS = [
        OperatorAccountSettings(
            username="admin",
            password_hash=hash_password("AdminPass!234"),
            role="admin",
        )
    ]

    login_response = await login(
        LoginRequest(username="admin", password="AdminPass!234"),
        _request_with_ip("127.0.0.1"),
    )
    assert login_response.username == "admin"
    assert login_response.role == "admin"

    principal, _ = JWTService.decode_token(
        login_response.refresh_token,
        expected_type="refresh",
    )
    assert principal.username == "admin"

    refresh_response = await refresh(RefreshRequest(refresh_token=login_response.refresh_token))
    assert refresh_response.access_token != login_response.access_token
    assert await is_token_revoked(principal.token_id) is True

    access_principal, _ = JWTService.decode_token(
        refresh_response.access_token,
        expected_type="access",
    )
    await logout(refresh_response.access_token)
    assert await is_token_revoked(access_principal.token_id) is True


@pytest.mark.asyncio
async def test_login_rejects_invalid_password():
    settings = get_settings()
    settings.SECURITY_OPERATORS = [
        OperatorAccountSettings(
            username="admin",
            password_hash=hash_password("AdminPass!234"),
            role="admin",
        )
    ]
    with pytest.raises(AuthenticationError):
        await login(
            LoginRequest(username="admin", password="WrongPass!234"),
            _request_with_ip("127.0.0.2"),
        )


@pytest.mark.asyncio
async def test_check_agent_blocks_replayed_nonce():
    agent_instance = TrafficAgent()
    agent_id = uuid.uuid4()
    agent_model = Agent(
        id=agent_id,
        name="traffic_agent",
        domain="traffic",
        status="active",
        public_key=agent_instance.get_public_key_pem(),
        capabilities=[],
    )
    await agent_model.insert()

    signed_payload = {
        "agent_name": "traffic_agent",
        "action_type": "close_road",
        "payload": {"road_id": "MAIN_ST"},
        "nonce": "replayed-nonce",
    }
    signature = agent_instance.sign_payload(signed_payload)

    await check_agent(str(agent_id), signed_payload, signature)
    with pytest.raises(ReplayAttackError):
        await check_agent(str(agent_id), signed_payload, signature)
