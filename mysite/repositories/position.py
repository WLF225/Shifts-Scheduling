"""Repository for position rows."""
from database.models import Position
from repositories.base import BaseRepository


class PositionRepository(BaseRepository[Position]):
    """Queries over positions."""

    model = Position

    def by_name(self, name: str) -> Position | None:
        """The position with this name, or None."""
        return (
            self.session.query(Position)
            .filter(Position.name == name)
            .first()
        )

    def get_or_create(self, name: str) -> Position:
        """The named position, created if missing."""
        existing = self.by_name(name)
        if existing is not None:
            return existing
        return self.create(name=name)
