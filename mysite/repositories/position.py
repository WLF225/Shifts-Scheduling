from database.models import Position
from repositories.base import BaseRepository


class PositionRepository(BaseRepository[Position]):
    model = Position
