"""Repository for schedule rows."""
from typing import Sequence

from database.models import Schedule
from repositories.base import BaseRepository
from repositories.exceptions import InvalidFilter


class ScheduleRepository(BaseRepository[Schedule]):
    """Queries over schedules, scoped to their brand."""

    model = Schedule

    def for_brand(self, brand_pk: int) -> Sequence[Schedule]:
        """Every schedule belonging to this brand."""
        if brand_pk is None:
            raise InvalidFilter("brand_pk is required")
        return (
            self.session.query(Schedule)
            .filter(Schedule.brand_id == brand_pk)
            .all()
        )

    def schedule_for_brand(self, brand_pk: int, schedule_pk: int) -> Schedule | None:
        """One schedule, only within this brand."""
        if brand_pk is None or schedule_pk is None:
            raise InvalidFilter("brand_pk and schedule_pk are both required")
        return (
            self.session.query(Schedule)
            .filter(Schedule.brand_id == brand_pk, Schedule.id == schedule_pk)
            .one_or_none()
        )
