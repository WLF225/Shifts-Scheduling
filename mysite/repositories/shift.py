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
        """Every shift an employee works, reached through their jobs.

        The INNER JOIN on Job is load-bearing now that ``Shift.job_id`` is
        nullable: it drops unassigned slots, which is what makes the FREE/BUSY
        answer in ``EmployeeTimeViewSet`` correct - nobody is busy during a slot
        no one has been assigned to. Switching this to an ``outerjoin`` would
        quietly report every empty slot as time the employee is working.
        """
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
        """One employee's shifts within one schedule.

        Currently unused. Its only caller was the ``employees/<id>/schedules/
        <id>/shifts`` mount, which has been removed as a duplicate of the
        employee- and schedule-nested listings.
        """
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
        """The shift occupying one role's slot at one time on one day, if any.

        Currently unused. This was the lookup behind the collection-level PUT
        upsert, which no longer exists: a shift is now addressed by its own pk
        under its role, so nothing needs to find a row by its slot. Kept as a
        query the repository can still answer.

        The key is deliberately ``(role, date, starting_time)`` and not
        ``(role, date)``: a role routinely has several shifts on the same day -
        a morning and an evening Cashier, say - so the day alone does not
        identify one. It matches staffed and unstaffed rows alike.
        """
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

    def overlapping_for_employee(
        self,
        employee_pk: int,
        on_date: date_type,
        starting_time,
        finishing_time,
        exclude_shift_pk: int | None = None,
    ) -> Sequence[Shift]:
        """Shifts the employee already works that clash with a proposed span.

        Scoped to the *employee*, not to a job, brand, role or schedule: someone
        holding two jobs still only has one body, so a booking at another brand
        counts as a clash.

        Overlap is half-open - ``existing.starting < new.finishing`` and
        ``new.starting < existing.finishing`` - so a shift starting exactly when
        another finishes is not a clash.

        ``exclude_shift_pk`` drops one row from consideration; the shift PUT
        passes the row it is about to write, which would otherwise always clash
        with itself.
        """
        if employee_pk is None or on_date is None:
            raise InvalidFilter("employee_pk and date are both required")
        if starting_time is None or finishing_time is None:
            raise InvalidFilter("starting_time and finishing_time are both required")
        query = (
            self.session.query(Shift)
            .join(Job, Job.id == Shift.job_id)
            .filter(
                Job.employee_id == employee_pk,
                Shift.date == on_date,
                Shift.starting_time < finishing_time,
                Shift.finishing_time > starting_time,
            )
        )
        if exclude_shift_pk is not None:
            query = query.filter(Shift.id != exclude_shift_pk)
        return query.order_by(Shift.starting_time).all()
