"""Business rules for shifts and their staffing."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Sequence

from components.base import BaseComponent
from components.exceptions import NotFound, ValidationError
from components.parsing import (
    body_dict,
    has_key,
    parse_date,
    parse_int,
    parse_time,
    pick,
    present_keys,
)
from components.role import RoleComponent
from database.models import JobStatus, Shift
from repositories.job import JobRepository
from repositories.shift import ShiftRepository

STAFFING_KEYS = ("job_id", "employee_id")

TIME_KEYS = (
    "starting_time",
    "start_time",
    "finishing_time",
    "finish_time",
    "ending_time",
    "starting_date",
    "date",
)


class ShiftComponent(BaseComponent):
    """Creates unstaffed shifts, then staffs or retimes them."""

    def list(self, role_pk=None, employee_pk=None) -> Sequence[Shift]:
        """Shifts under one role, or one employee's."""
        shifts = self._repo(ShiftRepository)
        if employee_pk is not None:
            return shifts.for_employee(employee_pk)
        if role_pk is not None:
            return shifts.for_role(role_pk)
        raise RuntimeError("ShiftComponent.list needs role_pk or employee_pk; a shift listing is always addressed under a role or an employee")

    def get(self, pk=None, role_pk=None, schedule_pk=None, employee_pk=None) -> Shift:
        """One shift, 404 unless every named parent matches."""
        shift = self._repo(ShiftRepository).get(pk)
        if shift is None:
            raise NotFound("Shift not found")

        role = shift.role
        schedule = role.schedule if role is not None else None
        job = shift.job
        mismatched = ((role_pk is not None and str(shift.role_id) != str(role_pk))
            or (schedule_pk is not None and (schedule is None or str(schedule.id) != str(schedule_pk)))
            or (employee_pk is not None and (job is None or str(job.employee_id) != str(employee_pk))) )
        if mismatched:
            raise NotFound(f"Shift {pk} not found here")
        return shift

    def create(self, data: Any, schedule_pk=None, role_pk=None) -> Shift:
        """Open an unstaffed slot; rejects naming anyone."""
        role = self._role(schedule_pk, role_pk)

        body = body_dict(data)
        if pick(body, "employee_id") is not None or pick(body, "job_id") is not None:
            schedule = role.schedule
            brand = schedule.brand_id if schedule is not None else "<brand_id>"
            raise ValidationError(
                "A shift is created unassigned; PUT "
                f"/api/v1/brands/{brand}/schedules/{schedule_pk}/roles/{role.id}"
                "/shifts/<shift_id> to staff it"
            )
        fields = self._times(body)
        self._check_week(role, fields["date"])

        return self._repo(ShiftRepository).create(
            job_id=None, role_id=role.id, **fields
        )

    def update(self, data: Any, pk=None, schedule_pk=None, role_pk=None) -> Shift:
        """Staffs, retimes, or unstaffs one shift."""
        role = self._role(schedule_pk, role_pk)

        shifts = self._repo(ShiftRepository)
        shift = shifts.get(pk)
        if shift is None or str(shift.role_id) != str(role.id):
            raise NotFound(f"Shift {pk} not found in role {role.id}")

        body = body_dict(data)

        changes = {}
        if has_key(body, *TIME_KEYS):
            changes.update(self._times(body))
            self._check_week(role, changes["date"])

        fields = {
            "date": changes.get("date", shift.date),
            "starting_time": changes.get("starting_time", shift.starting_time),
            "finishing_time": changes.get("finishing_time", shift.finishing_time),
        }

        intent = self._staffing_intent(body)
        if intent == "unstaff":
            changes["job_id"] = None
        elif intent == "staff":
            job = self._resolve_job(role, body)
            self._check_assignment(job, role, fields, exclude_shift_id=shift.id)
            changes["job_id"] = job.id
        elif changes:
            # Retiming a staffed shift must not create a clash.
            job = shift.job
            if job is not None:
                self._check_assignment(job, role, fields, exclude_shift_id=shift.id)

        if changes:
            shift = shifts.update(shift, **changes)
        return shift

    @staticmethod
    def _staffing_intent(body: dict) -> str | None:
        """Read the body as staff, unstaff, or neither."""
        present = present_keys(body, *STAFFING_KEYS)
        if not present:
            return None

        nulls = [name for name in present if pick(body, name) is None]
        if len(nulls) == len(present):
            return "unstaff"
        if not nulls:
            return "staff"

        filled = [name for name in present if name not in nulls]
        raise ValidationError(
            "Contradictory staffing: "
            + ", ".join(f"{name} is null" for name in nulls)
            + " but "
            + ", ".join(f"{name} is {pick(body, name)!r}" for name in filled)
            + ". Send every one of "
            + ", ".join(STAFFING_KEYS)
            + " as null to unstaff this shift, or send only the one that names "
            "who should work it"
        )

    def _resolve_job(self, role, body):
        """The job named, else the role's sole holder."""
        jobs = self._repo(JobRepository)

        schedule = role.schedule
        if schedule is None:
            raise ValidationError(
                f"Role {role.id} has no schedule, so its brand is unknown"
            )
        brand_id = schedule.brand_id

        raw_job_id = pick(body, "job_id")
        if raw_job_id is not None:
            job = jobs.get(parse_int(raw_job_id, "job_id"))
            if job is None:
                raise ValidationError(f"Job {raw_job_id} not found")
            if job.brand_id != brand_id:
                raise ValidationError(
                    f"Job {job.id} belongs to brand {job.brand_id}, not brand "
                    f"{brand_id}, so it cannot staff this role"
                )
            raw_employee_id = pick(body, "employee_id")
            if raw_employee_id is not None:
                employee_id = parse_int(raw_employee_id, "employee_id")
                if job.employee_id != employee_id:
                    raise ValidationError(
                        f"Job {job.id} belongs to employee {job.employee_id}, not "
                        f"employee {employee_id}; send only one of job_id or "
                        "employee_id"
                    )
            return job

        raw_employee_id = pick(body, "employee_id")
        if raw_employee_id is not None:
            employee_id = parse_int(raw_employee_id, "employee_id")
            job = jobs.for_brand_and_employee(brand_id, employee_id)
            if job is None:
                raise ValidationError(
                    f"Employee {employee_id} has no job at brand {brand_id}"
                )
            return job

        candidates = jobs.by_position_name(brand_id, role.name, status=JobStatus.ACTIVE)
        if not candidates:
            raise ValidationError(
                f"No active employee for role {role.name!r} in this brand; "
                "pass an explicit job_id or employee_id"
            )
        if len(candidates) > 1:
            ids = ", ".join(str(job.employee_id) for job in candidates)
            raise ValidationError(
                f"{len(candidates)} active employees hold role {role.name!r} in this "
                f"brand (employee ids: {ids}); pass an explicit job_id or employee_id"
            )
        return candidates[0]

    def _check_assignment(self, job, role, fields, exclude_shift_id=None) -> None:
        """Position matches, job active, employee not double-booked."""
        employee = job.employee
        who = f"Employee {job.employee_id}" + (
            f" ({employee.name})" if employee is not None else ""
        )

        position_name = job.position.name if job.position is not None else None
        if position_name != role.name:
            raise ValidationError(
                f"{who} is {position_name!r} at brand {job.brand_id}, so they cannot "
                f"fill role {role.name!r}"
            )

        if job.status != JobStatus.ACTIVE:
            raise ValidationError(
                f"{who} is inactive at brand {job.brand_id} (job {job.id}) and "
                "cannot be scheduled"
            )

        clashes = self._repo(ShiftRepository).overlapping_for_employee(
            job.employee_id,
            fields["date"],
            fields["starting_time"],
            fields["finishing_time"],
            exclude_shift_pk=exclude_shift_id,
        )
        if clashes:
            clash = clashes[0]
            clash_role = clash.role
            clash_schedule = clash_role.schedule if clash_role is not None else None
            clash_brand = clash_schedule.brand if clash_schedule is not None else None
            where = f" for role {clash_role.name!r}" if clash_role is not None else ""
            where += f" at brand {clash_brand.name!r}" if clash_brand is not None else ""
            raise ValidationError(
                f"{who} is already booked on {fields['date'].isoformat()} from "
                f"{clash.starting_time.isoformat()} to "
                f"{clash.finishing_time.isoformat()}{where} (shift {clash.id}), which "
                f"overlaps {fields['starting_time'].isoformat()}-"
                f"{fields['finishing_time'].isoformat()}"
            )

    def _role(self, schedule_pk, role_pk):
        """The role this write is addressed under."""
        return RoleComponent(self.session).for_write(schedule_pk, role_pk)

    @staticmethod
    def _check_week(role, on_date) -> None:
        """Reject a date outside the schedule's seven days."""
        schedule = role.schedule
        if schedule is None:
            raise ValidationError(
                f"Role {role.id} has no schedule, so its week is unknown"
            )

        first = schedule.starting_date
        last = first + timedelta(days=6)
        if not (first <= on_date <= last):
            raise ValidationError(
                f"{on_date.isoformat()} is outside the schedule week "
                f"[{first.isoformat()}, {last.isoformat()}]"
            )

    @staticmethod
    def _times(body: dict) -> dict:
        """Parse date and span; finish must follow start."""
        starting = parse_time(pick(body, "starting_time", "start_time"), "starting_time")
        finishing = parse_time(pick(body, "finishing_time", "finish_time", "ending_time"), "finishing_time")

        if finishing <= starting:
            raise ValidationError("finishing_time must be after starting_time")

        on_date = parse_date(pick(body, "starting_date", "date"), "starting_date")
        return {"starting_time": starting,
                "finishing_time": finishing,
                "date": on_date,}
