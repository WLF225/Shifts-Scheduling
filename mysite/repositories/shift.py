"""Repository for shift rows."""
from datetime import date as date_type
from typing import Sequence

from database.models import Job, Role, Shift
from repositories.base import BaseRepository
from repositories.exceptions import InvalidFilter


class ShiftRepository(BaseRepository[Shift]):
    """Queries over shifts, ordered by date and start."""

    model = Shift

    def for_role(self, role_pk: int) -> Sequence[Shift]:
        """This role's shifts, ordered by date and start."""
        if role_pk is None:
            raise InvalidFilter("role_pk is required")
        return (
            self.session.query(Shift)
            .filter(Shift.role_id == role_pk)
            .order_by(Shift.date, Shift.starting_time)
            .all()
        )

    def for_schedule(self, schedule_pk: int) -> Sequence[Shift]:
        """A schedule's shifts, reached through its roles."""
        if schedule_pk is None:
            raise InvalidFilter("schedule_pk is required")
        return (
            self.session.query(Shift)
            .join(Role, Role.id == Shift.role_id)
            .filter(Role.schedule_id == schedule_pk)
            .order_by(Shift.date, Shift.starting_time)
            .all()
        )

    def for_employee(self, employee_pk: int) -> Sequence[Shift]:
        """An employee's assigned shifts, reached through their jobs."""
        if employee_pk is None:
            raise InvalidFilter("employee_pk is required")
        return (
            self.session.query(Shift)
            .join(Job, Job.id == Shift.job_id)
            .filter(Job.employee_id == employee_pk)
            .order_by(Shift.date, Shift.starting_time)
            .all()
        )

    def for_employee_in_schedule(
        self, employee_pk: int, schedule_pk: int
    ) -> Sequence[Shift]:
        """One employee's shifts within one schedule."""
        if employee_pk is None or schedule_pk is None:
            raise InvalidFilter("employee_pk and schedule_pk are both required")
        return (
            self.session.query(Shift)
            .join(Job, Job.id == Shift.job_id)
            .join(Role, Role.id == Shift.role_id)
            .filter(Job.employee_id == employee_pk, Role.schedule_id == schedule_pk)
            .order_by(Shift.date, Shift.starting_time)
            .all()
        )

    def for_role_date_start(
        self, role_pk: int, on_date: date_type, starting_time
    ) -> Shift | None:
        """The shift in one role's slot, if any."""
        if role_pk is None or on_date is None or starting_time is None:
            raise InvalidFilter("role_pk, date and starting_time are all required")
        return (
            self.session.query(Shift)
            .filter(
                Shift.role_id == role_pk,
                Shift.date == on_date,
                Shift.starting_time == starting_time,
            )
            .order_by(Shift.id)
            .first()
        )

    def overlapping_for_employee(self, employee_pk: int, on_date: date_type, starting_time,
                                 finishing_time, exclude_shift_pk: int | None = None) -> Sequence[Shift]:
        """This employee's shifts overlapping the given interval."""
        if employee_pk is None or on_date is None:
            raise InvalidFilter("employee_pk and date are both required")
        if starting_time is None or finishing_time is None:
            raise InvalidFilter("starting_time and finishing_time are both required")
        query = (self.session.query(Shift)
            .join(Job, Job.id == Shift.job_id)
            .filter(Job.employee_id == employee_pk, Shift.date == on_date,
                    Shift.starting_time < finishing_time, Shift.finishing_time > starting_time))

        if exclude_shift_pk is not None:
            query = query.filter(Shift.id != exclude_shift_pk)
        return query.order_by(Shift.starting_time).all()
