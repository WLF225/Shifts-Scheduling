"""Issuing and verifying the two token types.

Access tokens are stateless HS256 JWTs: short-lived, never stored, verified
with no database round-trip. Refresh tokens are opaque random strings; only
their SHA-256 hash is stored, so a leaked database dump yields no usable
sessions.

Both are presented as ``Authorization: Bearer <token>``.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from django.conf import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_LIFETIME = timedelta(minutes=15)
REFRESH_TOKEN_LIFETIME = timedelta(days=14)


def _secret() -> str:
    return settings.SECRET_KEY


def issue_access_token(manager_id: int) -> tuple[str, datetime]:
    """Return a signed access JWT and the moment it expires."""
    now = datetime.now(timezone.utc)
    expires_at = now + ACCESS_TOKEN_LIFETIME
    payload = {
        "sub": str(manager_id),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM), expires_at


def decode_access_token(token: str) -> int:
    """Verify an access token and return the manager id it belongs to.

    Raises :class:`auth.exceptions.InvalidToken` on anything suspect: a bad
    signature, an expired token, or a refresh token presented where an access
    token was expected.
    """
    from authentication.exceptions import InvalidToken

    try:
        claims = jwt.decode(token, _secret(), algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise InvalidToken("Access token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidToken("Access token is invalid") from exc

    if claims.get("type") != "access":
        raise InvalidToken("Expected an access token")
    try:
        return int(claims["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidToken("Access token has no valid subject") from exc


def generate_refresh_token() -> tuple[str, str, datetime]:
    """Mint a refresh token.

    Returns ``(raw, hashed, expires_at)``. Only ``hashed`` is stored; ``raw``
    goes to the client once and cannot be recovered afterwards.
    """
    raw = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + REFRESH_TOKEN_LIFETIME
    return raw, hash_refresh_token(raw), expires_at


def hash_refresh_token(raw: str) -> str:
    """SHA-256 of the raw token. Fast by design: this is a high-entropy
    random string, not a password, so a slow KDF buys nothing here."""
    return hashlib.sha256(raw.encode()).hexdigest()
