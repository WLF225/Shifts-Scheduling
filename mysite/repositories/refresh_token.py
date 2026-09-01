from datetime import datetime, timezone

from database.models import RefreshToken
from repositories.base import BaseRepository


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    model = RefreshToken

    def by_hash(self, token_hash: str) -> RefreshToken | None:
        return self.first(token_hash=token_hash)

    def revoke(self, token: RefreshToken) -> RefreshToken:
        """Mark a single token spent. Idempotent."""
        if token.revoked_at is None:
            self.update(token, revoked_at=datetime.now(timezone.utc))
        return token

    def revoke_all_for(self, manager_id: int) -> int:
        """Revoke every live token for a manager (logout-everywhere, reuse response)."""
        now = datetime.now(timezone.utc)
        live = [t for t in self.list(manager_id=manager_id) if t.revoked_at is None]
        for token in live:
            token.revoked_at = now
        if live:
            self.commit()
        return len(live)
