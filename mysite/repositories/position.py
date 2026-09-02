from database.models import Position
from repositories.base import BaseRepository


class PositionRepository(BaseRepository[Position]):
    model = Position

    def by_name(self, name: str) -> Position | None:
        """Case-insensitive lookup by position name."""
        return (
            self.session.query(Position)
            .filter(Position.name == name)
            .first()
        )

    def get_or_create(self, name: str) -> Position:
        """Return the position with ``name``, creating it if it does not exist."""
        existing = self.by_name(name)
        if existing is not None:
            return existing
        return self.create(name=name)
