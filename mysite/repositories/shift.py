from database.models import Shift
from repositories.base import BaseRepository


class ShiftRepository(BaseRepository[Shift]):
    model = Shift
