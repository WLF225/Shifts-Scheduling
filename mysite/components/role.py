"""Business rules for roles."""
from __future__ import annotations

from typing import Any, Sequence

from components.base import BaseComponent
from components.exceptions import NotFound
from components.parsing import body_dict, pick, require_text
from components.schedule import ScheduleComponent
from database.models import Role
from repositories.role import RoleRepository


class RoleComponent(BaseComponent):
    """Reads and creates roles inside one schedule."""

    def get(self, pk, schedule_pk) -> Role:
        """One role, scoped to its schedule."""
        role = self._repo(RoleRepository).role_for_schedule(schedule_pk, pk)
        if role is None:
            raise NotFound("Role not found")
        return role

    def list(self, schedule_pk) -> Sequence[Role]:
        """One schedule's roles."""
        return self._repo(RoleRepository).for_schedule(schedule_pk)

    def create(self, data: Any, schedule_pk, brand_pk) -> Role:
        """Add a role to a brand's schedule."""
        schedule = ScheduleComponent(self.session).require(schedule_pk, brand_pk=brand_pk)

        body = body_dict(data)
        name = require_text(pick(body, "name"), "name")

        return self._repo(RoleRepository).create(name=name, schedule_id=schedule.id)

    def for_write(self, schedule_pk, role_pk) -> Role:
        """The role a shift write is addressed under."""
        role = self._repo(RoleRepository).role_for_schedule(schedule_pk, role_pk)

        if role is None:
            raise NotFound(f"Role {role_pk} not found in schedule {schedule_pk}")
        return role
