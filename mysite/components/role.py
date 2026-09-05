
from __future__ import annotations

from typing import Any, Sequence

from components.base import BaseComponent
from components.exceptions import NotFound, ValidationError
from components.parsing import body_dict, pick, require_text
from components.schedule import ScheduleComponent
from database.models import Role
from repositories.role import RoleRepository


class RoleComponent(BaseComponent):

    def get(self, pk=None, schedule_pk=None) -> Role:
        role = self._repo(RoleRepository).role_for_schedule(schedule_pk, pk)
        if role is None:
            raise NotFound("Role not found")
        return role

    def list(self, schedule_pk=None) -> Sequence[Role]:
        return self._repo(RoleRepository).for_schedule(schedule_pk)

    def create(self, data: Any, schedule_pk=None, brand_pk=None) -> Role:
        """Add a role to a schedule.

        Both parents are required. ``brand_pk`` is not decoration: it is passed
        to :meth:`components.schedule.ScheduleComponent.require` so the
        schedule is resolved *within* the brand, which stops a role being
        written into another brand's schedule by pk.
        """
        if schedule_pk is None or brand_pk is None:
            raise ValidationError(
                "A role belongs to a schedule and cannot be created on its own; "
                "POST /api/v1/brands/<brand_id>/schedules/<schedule_id>/roles "
                "instead"
            )

        schedule = ScheduleComponent(self.session).require(schedule_pk, brand_pk=brand_pk)

        body = body_dict(data)
        name = require_text(pick(body, "name"), "name")

        return self._repo(RoleRepository).create(name=name, schedule_id=schedule.id)

    def for_write(self, schedule_pk, role_pk) -> Role:

        if role_pk is None or schedule_pk is None:
            raise ValidationError(
                "A shift is addressed under a role: "
                "/api/v1/brands/<brand_id>/schedules/<schedule_id>/roles/"
                "<role_id>/shifts to create one, "
                "/api/v1/brands/<brand_id>/schedules/<schedule_id>/roles/"
                "<role_id>/shifts/<shift_id> to retime or staff one")

        role = self._repo(RoleRepository).role_for_schedule(schedule_pk, role_pk)

        if role is None:
            raise NotFound(f"Role {role_pk} not found in schedule {schedule_pk}")
        return role
