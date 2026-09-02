from datetime import date as date_type
from typing import Sequence

from database.models import Job, Role, Shift
from repositories.base import BaseRepository
from repositories.exceptions import InvalidFilter


class ShiftRepository(BaseRepository[Shift]):
    model = Shift

    def for_role(self, role_pk: int) -> Sequence[Shift]:
        if role_pk is None:
            raise InvalidFilter("role_pk is required")
        return (
            self.session.query(Shift)
            .filter(Shift.role_id == role_pk)
            .order_by(Shift.date, Shift.starting_time)
            .all()
        )

    def for_schedule(self, schedule_pk: int) -> Sequence[Shift]:
        """Every shift under a schedule, reached through that schedule's roles."""
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
        """Every shift an employee works, reached through their jobs."""
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

    def for_role_job_date(
        self, role_pk: int, job_pk: int, on_date: date_type
    ) -> Shift | None:
        """The single shift on a role for one job on one day, if any.

        This is the lookup behind the collection-level PUT upsert: a (role, job,
        date) triple identifies at most one planned shift.
        """
        if role_pk is None or job_pk is None or on_date is None:
            raise InvalidFilter("role_pk, job_pk and date are all required")
        return (
            self.session.query(Shift)
            .filter(
                Shift.role_id == role_pk,
                Shift.job_id == job_pk,
                Shift.date == on_date,
            )
            .order_by(Shift.starting_time)
            .first()
        )
