from database.models import Manager
from repositories.base import BaseRepository


class ManagerRepository(BaseRepository[Manager]):
    model = Manager

    def by_username(self, username: str) -> Manager | None:
        return self.first(username=username)

    def by_email(self, email: str) -> Manager | None:
        return self.first(email=email)
