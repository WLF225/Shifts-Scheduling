"""Authentication use-cases.

Password hashing happens here and only here: the raw password arrives from the
request, is hashed with Django's PBKDF2 hasher, and is never stored or logged.
"""
from __future__ import annotations

from datetime import datetime, timezone

from django.contrib.auth.hashers import check_password, make_password

from authentication.exceptions import (
    InactiveAccount,
    InvalidCredentials,
    InvalidToken,
    TokenReuse,
    UsernameTaken,
)
from authentication.tokens import (
    generate_refresh_token,
    hash_refresh_token,
    issue_access_token,
)
from database.models import Manager
from repositories.manager import ManagerRepository
from repositories.refresh_token import RefreshTokenRepository


class AuthService:
    def __init__(self, managers=None, refresh_tokens=None) -> None:
        # Session-injectable, matching BaseRepository, so tests can roll back.
        self.managers = managers or ManagerRepository()
        self.refresh_tokens = refresh_tokens or RefreshTokenRepository()

    # -------------------------------------------------------------- register

    def register(self, username: str, password: str, email: str | None = None) -> Manager:
        if self.managers.by_username(username):
            raise UsernameTaken(f"Username {username!r} is already taken")
        if email and self.managers.by_email(email):
            raise UsernameTaken(f"Email {email!r} is already registered")

        return self.managers.create(
            username=username,
            email=email,
            password_hash=make_password(password),
            is_active=True,
        )

    # ----------------------------------------------------------------- login

    def login(self, username: str, password: str) -> dict:
        manager = self.managers.by_username(username)

        # Hash even when the user is unknown, so a missing account and a wrong
        # password take the same time and cannot be told apart by timing.
        stored = manager.password_hash if manager else make_password("")
        matched = check_password(password, stored)

        if manager is None or not matched:
            raise InvalidCredentials()
        if not manager.is_active:
            raise InactiveAccount()

        return self._issue_pair(manager)

    # --------------------------------------------------------------- refresh

    def refresh(self, raw_refresh_token: str) -> dict:
        """Exchange a refresh token for a new pair, rotating the old one.

        If a token that was already spent is presented again, every live token
        for that manager is revoked: either the token leaked, or a stolen copy
        is racing the real client, and both cases warrant ending the sessions.
        """
        token = self.refresh_tokens.by_hash(hash_refresh_token(raw_refresh_token))
        if token is None:
            raise InvalidToken("Refresh token is invalid")

        if token.revoked_at is not None:
            self.refresh_tokens.revoke_all_for(token.manager_id)
            raise TokenReuse()

        if self._expired(token.expires_at):
            raise InvalidToken("Refresh token has expired")

        manager = self.managers.get(token.manager_id)
        if manager is None:
            raise InvalidToken("Refresh token is invalid")
        if not manager.is_active:
            raise InactiveAccount()

        self.refresh_tokens.revoke(token)
        return self._issue_pair(manager)

    # ---------------------------------------------------------------- logout

    def logout(self, raw_refresh_token: str) -> None:
        """Revoke one session. Silent when the token is already gone or spent."""
        token = self.refresh_tokens.by_hash(hash_refresh_token(raw_refresh_token))
        if token is not None:
            self.refresh_tokens.revoke(token)

    def logout_everywhere(self, manager_id: int) -> int:
        return self.refresh_tokens.revoke_all_for(manager_id)

    # ------------------------------------------------------------- internals

    def _issue_pair(self, manager: Manager) -> dict:
        access, access_expires = issue_access_token(manager.id)
        raw_refresh, hashed, refresh_expires = generate_refresh_token()

        self.refresh_tokens.create(
            manager_id=manager.id,
            token_hash=hashed,
            expires_at=refresh_expires,
        )
        return {
            "manager": manager,
            "access_token": access,
            "refresh_token": raw_refresh,
            "token_type": "Bearer",
            "expires_at": access_expires,
        }

    @staticmethod
    def _expired(expires_at: datetime) -> bool:
        # MySQL hands back naive datetimes; treat them as the UTC they were stored as.
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at <= datetime.now(timezone.utc)
