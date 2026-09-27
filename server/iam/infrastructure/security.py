"""Default IAM security adapters."""

from __future__ import annotations

from datetime import UTC, datetime
from secrets import token_urlsafe
from typing import Any

import jwt
from pwdlib import PasswordHash

from ..application.dto import IssuedToken, TokenClaims
from ..application.ports import OidcIdentity
from ..domain.services import OidcClaimsValidator


class PwdlibPasswordHasher:
    """Argon2 password hashing adapter."""

    def __init__(self) -> None:
        self._hasher = PasswordHash.recommended()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        return self._hasher.verify(password, password_hash)


class SecureApiKeySecretGenerator:
    """Generate a high-entropy API key secret once for the caller."""

    def generate(self) -> str:
        return token_urlsafe(32)


class PyJwtTokenIssuer:
    """JWT access-token adapter."""

    def __init__(self, secret: str, algorithm: str = "HS256") -> None:
        self.secret, self.algorithm = secret, algorithm

    def issue(self, claims: TokenClaims) -> IssuedToken:
        return IssuedToken(
            jwt.encode(claims.as_dict(), self.secret, algorithm=self.algorithm),
            expires_at=claims.expires_at,
        )


class StaticOidcTokenVerifier:
    """Small deterministic verifier useful for development and tests."""

    def __init__(self, identities: dict[str, tuple[str, str]]) -> None:
        self.identities = identities

    async def verify(self, token: str) -> OidcIdentity:
        try:
            subject, email = self.identities[token]
        except KeyError as error:
            raise ValueError("invalid OIDC token") from error
        OidcClaimsValidator.validate(subject=subject, email=email)
        return _OidcIdentity(subject, email)


class _OidcIdentity:
    def __init__(self, subject: str, email: str) -> None:
        self.subject, self.email = subject, email
