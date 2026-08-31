from database.models import Role
from repositories.base import BaseRepository


class RoleRepository(BaseRepository[Role]):
    model = Role
