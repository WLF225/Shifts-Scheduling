from database.models import Schedule
from repositories.base import BaseRepository


class ScheduleRepository(BaseRepository[Schedule]):
    model = Schedule
