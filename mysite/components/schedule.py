"""Business rules for schedules."""
from __future__ import annotations

from typing import Any, Sequence

from components.base import BaseComponent
from components.brand import BrandComponent
from components.exceptions import NotFound
from components.parsing import body_dict, parse_date, pick
from database.models import Schedule
from repositories.schedule import ScheduleRepository


class ScheduleComponent(BaseComponent):
    """Reads and writes schedules within their brand."""

    def get(self, pk, brand_pk) -> Schedule:
        """One schedule, scoped to the brand owning it."""
        schedule = self._repo(ScheduleRepository).schedule_for_brand(brand_pk, pk)
        if schedule is None:
            raise NotFound("Schedule not found")
        return schedule

    def list(self, brand_pk) -> Sequence[Schedule]:
        """One brand's schedules; there is no global listing."""
        return self._repo(ScheduleRepository).for_brand(brand_pk)

    def create(self, data: Any, brand_pk) -> Schedule:
        """Open a schedule for a brand."""
        brand = BrandComponent(self.session).require(brand_pk)

        body = body_dict(data)
        starting_date = parse_date(pick(body, "starting_date", "date"), "starting_date")

        return self._repo(ScheduleRepository).create(brand_id=brand.id, starting_date=starting_date)

    def require(self, pk, brand_pk) -> Schedule:
        """The brand-scoped schedule a role is created under."""
        schedule = self._repo(ScheduleRepository).schedule_for_brand(brand_pk, pk)
        if schedule is None:
            raise NotFound(f"Schedule {pk} not found in brand {brand_pk}")
        return schedule
