from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from app.config import get_settings
from app.core.exceptions import AuthenticationError, InvalidTokenError, TokenExpiredError
from app.security.principals import AuthenticatedPrincipal, TokenType, UserRole


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JWTService:
    """Issue and verify RSA-signed JWTs for human operators."""

    @staticmethod
    def _base_claims(username: str, role: UserRole, token_type: TokenType, expires_at: datetime) -> dict[str, Any]:
        settings = get_settings()
        issued_at = _utc_now()
        return {
            "sub": username,
            "role": role,
            "type": token_type,
            "jti": str(uuid.uuid4()),
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "iat": int(issued_at.timestamp()),
            "nbf": int(issued_at.timestamp()),
            "exp": int(expires_at.timestamp()),
        }

    @classmethod
    def create_access_token(cls, username: str, role: UserRole) -> tuple[str, datetime]:
        settings = get_settings()
        expires_at = _utc_now() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        claims = cls._base_claims(username, role, "access", expires_at)
        token = jwt.encode(claims, settings.rsa_private_key, algorithm=settings.JWT_ALGORITHM)
        return token, expires_at

    @classmethod
    def create_refresh_token(cls, username: str, role: UserRole) -> tuple[str, datetime]:
        settings = get_settings()
        expires_at = _utc_now() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        claims = cls._base_claims(username, role, "refresh", expires_at)
        token = jwt.encode(claims, settings.rsa_private_key, algorithm=settings.JWT_ALGORITHM)
        return token, expires_at

    @classmethod
    def decode_token(cls, token: str, expected_type: TokenType | None = None) -> tuple[AuthenticatedPrincipal, datetime]:
        settings = get_settings()
        try:
            payload = jwt.decode(
                token,
                settings.rsa_public_key,
                algorithms=[settings.JWT_ALGORITHM],
                audience=settings.JWT_AUDIENCE,
                issuer=settings.JWT_ISSUER,
            )
        except JWTError as exc:
            message = str(exc).lower()
            if "expired" in message:
                raise TokenExpiredError("JWT has expired.") from exc
            raise InvalidTokenError("JWT verification failed.") from exc

        token_type = payload.get("type")
        if expected_type and token_type != expected_type:
            raise AuthenticationError(f"Expected a {expected_type} token.")

        try:
            expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)
            principal = AuthenticatedPrincipal(
                username=payload["sub"],
                role=payload["role"],
                token_id=payload["jti"],
                token_type=token_type,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidTokenError("JWT claims are incomplete.") from exc

        return principal, expires_at
