from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel


UserRole = Literal["admin", "operator", "auditor"]
TokenType = Literal["access", "refresh"]


class AuthenticatedPrincipal(BaseModel):
    """Authenticated operator principal decoded from a JWT."""

    username: str
    role: UserRole
    token_id: str
    token_type: TokenType

    @property
    def subject(self) -> str:
        return f"user:{self.username}"

    @property
    def principal_id(self) -> uuid.UUID:
        return uuid.uuid5(uuid.NAMESPACE_URL, f"ai-city-governor:{self.username}:{self.role}")
