"""Business rules for shifts - the only tier that decides who works when.

Job resolution and the four eligibility rules live here rather than in a shared
``jobs.py`` because staffing a shift is their only caller. ``_resolve_job``
answers "which job does this body mean", and it only means anything relative to
a role: all three of its branches are scoped to the brand that owns the role's
schedule, and the last one reads the role's *name* as a position name. Split
into a job module, the pair would be two halves of one decision sitting a file
apart, and the rule that they are checked together - always, on every write
that can put a person on a slot - would stop being visible.
"""
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
from database.models import Shift
from repositories.job import JobRepository
from repositories.shift import ShiftRepository

# The body keys that name a person, in ``_resolve_job``'s precedence order.
STAFFING_KEYS = ("job_id", "employee_id")

# The body keys :meth:`ShiftComponent._times` accepts.
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
    """Reads and writes shifts, and owns every staffing rule."""

    # --------------------------------------------------------------- reads

    def list(self, role_pk=None, schedule_pk=None, employee_pk=None) -> Sequence[Shift]:
        """Shifts under whichever parent the URL names.

        The parents are tried most-specific first, matching the two mounts: an
        employee listing is that person's calendar, a role listing is one
        slot's history. Those are the only two, so there is no fall-through
        branch and no unscoped listing - every shift a caller can list is
        listed under a parent that names who it is for or what slot it fills.

        ``schedule_pk`` is still a parameter because the role-nested mount
        captures it, but it is never the *sole* parent of a read: the
        ``schedules/{schedule_pk}/shifts`` mount is gone, so a schedule alone
        no longer addresses a listing. It is used for scoping in :meth:`get`.

        The final ``raise`` is **unreachable through routing**: both mounts are
        nested, so DRF always supplies one of the two parents. It is a guard
        against a future registration that forgets one, or a direct call from a
        script - a wiring mistake, not a bad request, which is why it is not a
        :class:`ValidationError`. A 400 there would blame the caller for a bug
        in this module, and returning ``[]`` instead would silently answer a
        parentless listing with "no shifts" rather than admitting it cannot
        scope the query at all.
        """
        shifts = self._repo(ShiftRepository)
        if employee_pk is not None:
            return shifts.for_employee(employee_pk)
        if role_pk is not None:
            return shifts.for_role(role_pk)
        raise RuntimeError(
            "ShiftComponent.list needs role_pk or employee_pk; a shift listing "
            "is always addressed under a role or an employee"
        )

    def get(self, pk=None, role_pk=None, schedule_pk=None, employee_pk=None) -> Shift:
        """One shift, scoped to whichever parents the URL names.

        A shift reached through the wrong role, schedule or employee is a 404
        rather than a 200: the URL asserts where the row lives, and answering
        with a shift from somewhere else would make the nesting a lie. The
        parents are read off the row's own relationships, so this costs no
        extra query.
        """
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

    # -------------------------------------------------------------- writes

    def create(self, data: Any, schedule_pk=None, role_pk=None) -> Shift:
        """Create an unstaffed slot: role, date and span, nobody on it.

        ``date``, ``starting_time`` and ``finishing_time`` are all required and
        the span must be non-empty; :meth:`_times` enforces both. The date must
        also land inside the schedule's own week, which :meth:`_check_week`
        enforces. Nobody is attached here, so none of the four eligibility rules
        can be checked yet - they belong to :meth:`update`.

        A body carrying ``employee_id`` or ``job_id`` is rejected rather than
        silently ignored: a caller sending one plainly expects the shift to come
        out staffed, and a 201 with ``employee_id: null`` would look like a bug.
        """
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

    def update(self, data: Any, pk=None, schedule_pk=None, role_pk=None, employee_pk=None) -> Shift:
        """Retime a shift, staff it, or unstaff it - the one write on a slot.

        The shift is addressed by its own pk and must really sit under the role
        the URL names, in the same spirit as :meth:`get`: reaching a shift
        through the wrong role is a 404, not a silent write to someone else's
        row. Only the role is checked here, because a role is the only parent a
        write is ever addressed under.

        The three time fields are optional here, unlike in :meth:`create`. A
        body with none of them is a pure re-assignment and keeps the shift's
        stored span; a body with any of them is parsed by :meth:`_times` in
        full, so a partial triple is a 400 rather than a half-moved shift, and
        the *new* date is put through :meth:`_check_week`. A body that does not
        touch the times is not week-checked at all: the stored date was already
        in the window when it was written, and re-checking it would turn an
        unrelated re-assignment into a 400.

        ``employee_id`` (or an explicit ``job_id``) staffs the shift, enforcing
        all four eligibility rules through :meth:`_resolve_job` - which pins the
        job to the role's brand, rule 1 - and :meth:`_check_assignment` -
        position name, active status and the employee's own calendar, rules 2-4.
        The rules are checked against the times being *written*, so retiming and
        staffing in one PUT is validated against the new span. Nothing is
        written unless every rule passes.

        Nulling *every* staffing key present unstaffs the slot; no rules apply,
        because taking someone off a shift can never create a clash. Omitting
        the keys entirely leaves the existing assignment alone. See
        :meth:`_staffing_intent` for what a half-null body does.

        ``employee_pk`` is accepted but unused: ``employees/<id>/shifts/<id>``
        no longer binds PUT at all, so no caller can reach this method without
        a role. :meth:`_role` still raises its 400 if one is somehow missing.
        """
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
            # Safe to read shift.job here: this branch never writes job_id.
            job = shift.job
            if job is not None:
                self._check_assignment(job, role, fields, exclude_shift_id=shift.id)

        if changes:
            shift = shifts.update(shift, **changes)
        return shift

    # ------------------------------------------------------------- staffing

    @staticmethod
    def _staffing_intent(body: dict) -> str | None:
        """Does this body staff the shift, unstaff it, or leave it alone?

        Returns ``"staff"``, ``"unstaff"``, or ``None`` for "no staffing key was
        sent". Split out because the previous inline version got this wrong:
        it gated on ``employee_id`` first and then read the value with a
        ``pick`` that tried ``employee_id`` first, while ``_resolve_job``
        resolves ``job_id`` first. So ``{"employee_id": null, "job_id": 7}``
        took the unstaff branch on the null it found in ``employee_id`` and
        wrote ``job_id = None`` - the exact opposite of the request, at 200,
        with all four eligibility rules skipped.

        The rule now, on the keys actually present:

        * none present - ``None``. The assignment is untouched.
        * every one present is null - ``"unstaff"``. Clearing is unambiguous
          however it is spelled.
        * every one present is non-null, and they agree - ``"staff"``.
          Agreement means the named job really is the named employee's job at
          this brand, which only :meth:`_resolve_job` can confirm, so it is
          checked there and not here.
        * anything else - a :class:`ValidationError`. A body that is half-null
          (``employee_id: null`` with ``job_id: 7``) is contradictory: one key
          says clear the slot and the other says fill it. Picking a winner by
          key order is how the bug happened, so the request is refused instead.
        """
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
        """Work out which job a shift belongs to.

        Three ways in, in order of precedence:

        1. An explicit ``job_id`` in the body.
        2. An ``employee_id``, pinned to the brand that owns the role's schedule.
        3. Nothing at all - in which case the role's *name* is read as a position
           name and the single active job for that position in the brand is used.

        All three are scoped to the brand that owns the role's schedule. An
        explicit ``job_id`` is no exception: accepting one from another brand
        would let a caller staff this role with someone who does not work here.

        When both ``job_id`` and ``employee_id`` are sent non-null, ``job_id``
        keeps its precedence - but the two must agree, because a body naming a
        job and an employee who do not belong together has no single meaning
        and silently honouring one of them is the class of bug
        :meth:`_staffing_intent` exists to stop.

        Returns the job; every failure raises, so there is no error tuple to
        unpack and no way for a caller to forget to check it.
        """
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

        candidates = jobs.by_position_name(brand_id, role.name, status="active")
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
        """Is this job allowed to work this role over this span?

        Called from every path that can put an employee on a shift, which today
        is :meth:`update` alone - staffing a slot, and retiming one that is
        already staffed - so the four rules are enforced in exactly one place.

        :meth:`_resolve_job` has already pinned the job to the role's brand
        (rule 1) on all three of its branches. What is left is:

        * the job's position must be the role it is being booked into. There is
          no FK between Position and Role, so they are matched by name, which is
          the convention the seed data already relies on;
        * the job must be active - a terminated employment cannot be scheduled;
        * the employee must be free, across *every* job they hold. Two brands is
          still one person.

        ``exclude_shift_id`` is the row the PUT is about to write; without it a
        shift would always be found to clash with itself.

        Returns nothing and raises :class:`ValidationError` on a violation, so
        a caller cannot proceed by ignoring a returned message.
        """
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

        if job.status != "active":
            raise ValidationError(
                f"{who} has job {job.id} at brand {job.brand_id} with status "
                f"{job.status!r}, not 'active', so they cannot be scheduled"
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

    # ------------------------------------------------------------ internals

    def _role(self, schedule_pk, role_pk):
        """The role this write is addressed under.

        Delegates to :meth:`components.role.RoleComponent.for_write` so the
        check reads identically from shift create and shift update, and shares
        this component's session.
        """
        return RoleComponent(self.session).for_write(schedule_pk, role_pk)

    @staticmethod
    def _check_week(role, on_date) -> None:
        """Does this date fall in the week the role's schedule covers?

        A schedule covers exactly one week, anchored to its own
        ``starting_date`` - whatever weekday that happens to be. A Friday-start
        schedule covers Friday to the following Thursday. So the window is
        ``[starting_date, starting_date + 6 days]``, inclusive at both ends,
        and nothing here cares which weekday it opens on.

        Called from both writes rather than folded into :meth:`_times`, which
        is a ``staticmethod`` over the body alone and has no role to ask. Giving
        it one would make date *parsing* depend on a schedule lookup; keeping
        the rule here leaves :meth:`_times` answering "what did the body say"
        and this answering "is that allowed", which is the same split
        :meth:`_resolve_job` and :meth:`_check_assignment` already use.

        An orphan role is treated as :meth:`_resolve_job` treats it - a
        :class:`ValidationError` naming the missing schedule, not an
        ``AttributeError`` on ``None.starting_date``.
        """
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
        """The three time columns, parsed. ``starting_date`` maps to ``date``.

        All three are demanded together: once a caller mentions any time key,
        a partial triple is a 400 rather than a half-moved shift. The keys this
        accepts are :data:`TIME_KEYS`, which is what :meth:`update` gates on,
        so the two agree on what counts as a time key.
        """
        starting = parse_time(pick(body, "starting_time", "start_time"), "starting_time")
        finishing = parse_time(pick(body, "finishing_time", "finish_time", "ending_time"), "finishing_time")

        if finishing <= starting:
            raise ValidationError("finishing_time must be after starting_time")

        on_date = parse_date(pick(body, "starting_date", "date"), "starting_date")
        return {"starting_time": starting,
                "finishing_time": finishing,
                "date": on_date,}
