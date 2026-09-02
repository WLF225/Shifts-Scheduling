from typing import Sequence

from database.models import Role
from repositories.base import BaseRepository
from repositories.exceptions import InvalidFilter


class RoleRepository(BaseRepository[Role]):
    model = Role

    def for_schedule(self, schedule_pk: int) -> Sequence[Role]:
        if schedule_pk is None:
            raise InvalidFilter("schedule_pk is required")
        return self.session.query(Role).filter(Role.schedule_id == schedule_pk).all()

    def role_for_schedule(self, schedule_pk: int, role_pk: int) -> Role | None:
        """A role, but only if it belongs to ``schedule_pk``."""
        if schedule_pk is None or role_pk is None:
            raise InvalidFilter("schedule_pk and role_pk are both required")
        return (
            self.session.query(Role)
            .filter(Role.schedule_id == schedule_pk, Role.id == role_pk)
            .one_or_none()
        )
