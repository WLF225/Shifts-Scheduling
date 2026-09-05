"""Business rules for schedules."""
from __future__ import annotations

from typing import Any, Sequence

from components.base import BaseComponent
from components.brand import BrandComponent
from components.exceptions import NotFound, ValidationError
from components.parsing import body_dict, parse_date, pick
from database.models import Schedule
from repositories.schedule import ScheduleRepository


class ScheduleComponent(BaseComponent):
    """Reads and writes schedules, always within the brand that owns them."""

    def get(self, pk=None, brand_pk=None) -> Schedule:
        """One schedule, scoped to the brand that owns it.

        ``brand_pk`` is required, not optional: every route reaching this
        component is mounted under ``brands/<id>/``, and answering without a
        brand would let a caller read another brand's schedule by guessing an
        id. The unscoped ``ScheduleRepository.get`` is deliberately not called
        from here.
        """
        if brand_pk is None:
            raise ValidationError(
                "A schedule is addressed under its brand: "
                "GET /api/v1/brands/<brand_id>/schedules/<schedule_id>"
            )

        schedule = self._repo(ScheduleRepository).schedule_for_brand(brand_pk, pk)
        if schedule is None:
            raise NotFound("Schedule not found")
        return schedule

    def list(self, brand_pk=None) -> Sequence[Schedule]:
        """One brand's schedules.

        Like :meth:`get`, ``brand_pk`` is required - there is no "every
        schedule in the system" listing, because there is no URL that could ask
        for one.
        """
        if brand_pk is None:
            raise ValidationError(
                "Schedules are listed under a brand: "
                "GET /api/v1/brands/<brand_id>/schedules"
            )
        return self._repo(ScheduleRepository).for_brand(brand_pk)

    def create(self, data: Any, brand_pk=None) -> Schedule:
        """Open a schedule for a brand."""
        if brand_pk is None:
            raise ValidationError(
                "A schedule must be created under a brand: "
                "POST /api/v1/brands/<brand_id>/schedules"
            )

        brand = BrandComponent(self.session).require(brand_pk)

        body = body_dict(data)
        starting_date = parse_date(
            pick(body, "starting_date", "date"), "starting_date"
        )

        return self._repo(ScheduleRepository).create(
            brand_id=brand.id, starting_date=starting_date
        )

    def require(self, pk, brand_pk=None) -> Schedule:
        """A schedule that must exist because a role is being created under it.

        ``brand_pk`` is required for the same reason :meth:`get` requires it:
        without it, ``POST /brands/1/schedules/<schedule of brand 2>/roles``
        would resolve the schedule by pk alone and write a role into another
        brand's schedule. Scoping the lookup makes that a 404.
        """
        if brand_pk is None:
            raise ValidationError(
                "A schedule is addressed under its brand: "
                "/api/v1/brands/<brand_id>/schedules/<schedule_id>"
            )
        schedule = self._repo(ScheduleRepository).schedule_for_brand(brand_pk, pk)
        if schedule is None:
            raise NotFound(f"Schedule {pk} not found in brand {brand_pk}")
        return schedule
