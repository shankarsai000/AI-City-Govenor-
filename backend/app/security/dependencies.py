from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.core.exceptions import AuthenticationError, AuthorizationError
from app.security.jwt_service import JWTService
from app.security.principals import AuthenticatedPrincipal, UserRole
from app.security.token_store import is_token_revoked

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_principal(token: str = Depends(oauth2_scheme)) -> AuthenticatedPrincipal:
    principal, _ = JWTService.decode_token(token, expected_type="access")
    if await is_token_revoked(principal.token_id):
        raise AuthenticationError("JWT has been revoked.")
    return principal


def require_roles(*allowed_roles: UserRole) -> Callable[[AuthenticatedPrincipal], AuthenticatedPrincipal]:
    async def _dependency(
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> AuthenticatedPrincipal:
        if principal.role not in allowed_roles:
            raise AuthorizationError(
                f"Role '{principal.role}' is not permitted for this operation.",
                details={"allowed_roles": list(allowed_roles)},
            )
        return principal

    return _dependency
