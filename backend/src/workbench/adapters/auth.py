"""RS256 token verification; permissions are looked up server side, never from JWT roles."""

import hashlib
from pathlib import Path
from typing import Any

import jwt

from workbench.contracts.intake import Principal
from workbench.platform.config import Settings
from workbench.platform.errors import AuthenticationRequired


class JWTVerifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.jwks = (
            jwt.PyJWKClient(settings.oidc_jwks_url, timeout=3)
            if settings.auth_mode == "oidc"
            else None
        )

    def claims(self, token: str) -> dict[str, Any]:
        try:
            key = (
                self.jwks.get_signing_key_from_jwt(token).key
                if self.jwks is not None
                else Path(self.settings.fixture_public_key).read_bytes()
            )
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self.settings.auth_issuer,
                audience=self.settings.auth_audience,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
            subject = claims["sub"]
            if not isinstance(subject, str) or not subject:
                raise AuthenticationRequired()
            if claims.get("token_use", "access") != "access":
                raise AuthenticationRequired()
            if self.settings.auth_mode == "oidc" and not (
                claims.get("token_use") == "access" or claims.get("typ") == "Bearer"
            ):
                raise AuthenticationRequired()
            return dict(claims)
        except (jwt.PyJWTError, OSError, ValueError) as error:
            raise AuthenticationRequired() from error

    def subject(self, token: str) -> str:
        return str(self.claims(token)["sub"])

    def principal(self, token: str) -> Principal:
        claims = self.claims(token)
        auth_time = claims.get("auth_time", 0)
        if not isinstance(auth_time, int) or isinstance(auth_time, bool):
            raise AuthenticationRequired()
        session = (
            claims.get("sid") or claims.get("jti") or hashlib.sha256(token.encode()).hexdigest()
        )
        if not isinstance(session, str) or not 1 <= len(session) <= 200:
            raise AuthenticationRequired()
        return Principal(
            issuer=str(claims["iss"]),
            subject=str(claims["sub"]),
            session_id=session,
            issued_at=int(claims["iat"]),
            expires_at=int(claims["exp"]),
            auth_time=auth_time,
            mfa=isinstance(claims.get("amr"), list) and "mfa" in claims["amr"],
        )
