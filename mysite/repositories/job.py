from database.models import Job
from repositories.base import BaseRepository


class JobRepository(BaseRepository[Job]):
    model = Job
