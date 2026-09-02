"""Views for the scheduling API.

Input coercion lives at the top of this module. The clients that drive this API
send dates as ``D/M/YYYY`` and times as bare integer hours, and they are
inconsistent about key casing (``job_ID`` vs ``job_id``). Rather than scatter
that tolerance through the viewsets, every conversion is a module-level helper
here that raises :class:`ParseError`, which the views turn into a 400.
"""
from __future__ import annotations

from datetime import date as date_type, datetime, time as time_type
from typing import Any, Iterable

from rest_framework import status, viewsets
from rest_framework.response import Response

from mysite import exceptions
from mysite.schemas import (
    BrandSchema,
    EmployeeSchema,
    RoleSchema,
    ScheduleSchema,
)
from repositories.brand import BrandRepository
from repositories.employee import EmployeeRepository
from repositories.job import JobRepository
from repositories.position import PositionRepository
from repositories.role import RoleRepository
from repositories.schedule import ScheduleRepository
from repositories.shift import ShiftRepository

# The window FREE slots are measured against.
WORKDAY_START = time_type(0, 0)
WORKDAY_END = time_type(23, 59)


# --------------------------------------------------------------- input parsing


class ParseError(ValueError):
    """A request field could not be coerced into the type the column needs."""


# Accepted date spellings; D/M/YYYY is tried first.
DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y")

# Accepted time spellings for the string form.
TIME_FORMATS = ("%H:%M:%S", "%H:%M", "%H")


def pick(data: dict[str, Any], *names: str, default: Any = None) -> Any:
    """Read the first present key out of ``data``, ignoring case.

    ``pick(body, "job_id")`` matches ``job_id``, ``job_ID`` and ``Job_Id``.
    """
    lowered = {str(key).lower(): value for key, value in data.items()}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return default


def parse_date(value: Any, field: str = "date") -> date_type:
    """Coerce ``value`` into a ``date``. Accepts ``D/M/YYYY`` and ISO."""
    if isinstance(value, date_type) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ParseError(f"{field} is required")
    text = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ParseError(
        f"{field} {text!r} is not a date; expected D/M/YYYY or YYYY-MM-DD"
    )


def parse_time(value: Any, field: str = "time") -> time_type:
    """Coerce ``value`` into a ``time``.

    An integer (or integer-looking string) is read as a whole hour, so ``8``
    becomes ``08:00``. ``"HH:MM"`` and ``"HH:MM:SS"`` are also accepted.
    """
    if isinstance(value, time_type):
        return value
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ParseError(f"{field} is required")
    if isinstance(value, bool):
        raise ParseError(f"{field} {value!r} is not a time")
    if isinstance(value, int):
        return _hour(value, field)
    if isinstance(value, float):
        if value != int(value):
            raise ParseError(f"{field} {value!r} is not a whole hour")
        return _hour(int(value), field)
    text = str(value).strip()
    if text.isdigit():
        return _hour(int(text), field)
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise ParseError(
        f"{field} {text!r} is not a time; expected an hour 0-24 or HH:MM"
    )


def parse_int(value: Any, field: str) -> int:
    """Coerce ``value`` into an ``int``, or raise :class:`ParseError`."""
    if isinstance(value, bool):
        raise ParseError(f"{field} {value!r} is not an integer")
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        raise ParseError(f"{field} {value!r} is not an integer") from None


def require_text(value: Any, field: str, max_length: int = 100) -> str:
    """A non-blank string, trimmed, within ``max_length``."""
    if value is None:
        raise ParseError(f"{field} is required")
    text = str(value).strip()
    if not text:
        raise ParseError(f"{field} must not be blank")
    if len(text) > max_length:
        raise ParseError(f"{field} must be at most {max_length} characters")
    return text


def parse_modes(raw: Any, allowed: Iterable[str]) -> list[str]:
    """Split a comma-separated ``mode`` query parameter and validate it.

    ``None`` or an empty value means "all modes", which is the documented
    default for ``/employees/<id>/times``.
    """
    allowed = [mode.lower() for mode in allowed]
    if raw is None or not str(raw).strip():
        return list(allowed)
    modes = []
    for part in str(raw).split(","):
        mode = part.strip().lower()
        if not mode:
            continue
        if mode not in allowed:
            raise ParseError(
                f"mode {part.strip()!r} is not valid; expected one of "
                + ", ".join(sorted(allowed))
            )
        if mode not in modes:
            modes.append(mode)
    if not modes:
        raise ParseError("mode must name at least one of " + ", ".join(sorted(allowed)))
    return modes


def _hour(hour: int, field: str) -> time_type:
    """An integer hour, where 24 is read as the end of the day."""
    if hour == 24:
        return time_type(23, 59)
    if not 0 <= hour <= 23:
        raise ParseError(f"{field} {hour!r} is not an hour between 0 and 24")
    return time_type(hour, 0)


# ------------------------------------------------------------------- viewsets

def _bad_request(message: str) -> Response:
    return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)


def _job_payload(job) -> dict:
    """A job as the API reports it: ids plus the position name it stands for."""
    return {
        "id": job.id,
        "brand_id": job.brand_id,
        "employee_id": job.employee_id,
        "position_id": job.position_id,
        "role": job.position.name if job.position is not None else None,
        "status": job.status,
    }


def _shift_payload(shift) -> dict:
    """A shift plus the context a caller needs to read it: role and brand."""
    role = shift.role
    schedule = role.schedule if role is not None else None
    brand = schedule.brand if schedule is not None else None
    return {
        "shift_id": shift.id,
        "job_id": shift.job_id,
        "role_id": shift.role_id,
        "role": role.name if role is not None else None,
        "schedule_id": schedule.id if schedule is not None else None,
        "brand_id": brand.id if brand is not None else None,
        "brand": brand.name if brand is not None else None,
        "date": shift.date.isoformat() if shift.date else None,
        "starting_time": shift.starting_time.isoformat() if shift.starting_time else None,
        "finishing_time": shift.finishing_time.isoformat() if shift.finishing_time else None,
    }


def _resolve_job(role, body):
    """Work out which job a shift belongs to.

    Three ways in, in order of precedence:

    1. An explicit ``job_id`` in the body.
    2. An ``employee_id``, pinned to the brand that owns the role's schedule.
    3. Nothing at all - in which case the role's *name* is read as a position
       name and the single active job for that position in the brand is used.

    All three are scoped to the brand that owns the role's schedule. An
    explicit ``job_id`` is no exception: accepting one from another brand would
    let a caller staff this role with someone who does not work here.

    Returns ``(job, error_message)``; exactly one of the two is ``None``.
    """
    jobs = JobRepository()

    schedule = role.schedule
    if schedule is None:
        return None, f"Role {role.id} has no schedule, so its brand is unknown"
    brand_id = schedule.brand_id

    raw_job_id = pick(body, "job_id")
    if raw_job_id is not None:
        job = jobs.get(parse_int(raw_job_id, "job_id"))
        if job is None:
            return None, f"Job {raw_job_id} not found"
        if job.brand_id != brand_id:
            return None, (
                f"Job {job.id} belongs to brand {job.brand_id}, not brand "
                f"{brand_id}, so it cannot staff this role"
            )
        return job, None

    raw_employee_id = pick(body, "employee_id")
    if raw_employee_id is not None:
        employee_id = parse_int(raw_employee_id, "employee_id")
        job = jobs.for_brand_and_employee(brand_id, employee_id)
        if job is None:
            return None, f"Employee {employee_id} has no job at brand {brand_id}"
        return job, None

    candidates = jobs.by_position_name(brand_id, role.name, status="active")
    if not candidates:
        return None, (
            f"No active employee for role {role.name!r} in this brand; "
            "pass an explicit job_id or employee_id"
        )
    if len(candidates) > 1:
        ids = ", ".join(str(job.employee_id) for job in candidates)
        return None, (
            f"{len(candidates)} active employees hold role {role.name!r} in this "
            f"brand (employee ids: {ids}); pass an explicit job_id or employee_id"
        )
    return candidates[0], None


class EmployeeViewSet(viewsets.ViewSet):
    def retrieve(self, request, pk:int | None = None, brand_pk:int | None = None) -> Response:
        """One employee, optionally scoped to a brand they hold a job at.

        The row is checked *before* it is dumped: marshmallow turns ``None``
        into ``{}``, so testing the serialised output would report a missing
        employee as an empty 200.
        """
        employee = EmployeeRepository()
        row = (
            employee.get(pk)
            if brand_pk is None
            else employee.employee_for_brand(brand_pk, pk)
        )
        if row is None:
            raise exceptions.NotFound(f"Employee {pk} not found")
        return Response(
            EmployeeSchema(many=False).dump(row), status=status.HTTP_200_OK
        )

    def list(self, request, brand_pk:int | None = None):
        """Every employee, or just those employed by one brand.

        An empty result is an empty list, not a 404 - "no employees match" is
        a valid answer to a collection query.
        """
        employee = EmployeeRepository()
        rows = (
            employee.list()
            if brand_pk is None
            else employee.employees_for_brand(brand_pk)
        )
        return Response(
            EmployeeSchema(many=True).dump(rows), status=status.HTTP_200_OK
        )

    def create(self, request, brand_pk:int | None = None) -> Response:
        """Hire an employee into a brand.

        Creates the Employee *and* the Job that links it to the brand, so the
        two never exist half-formed. ``roles`` names the position, which is
        created on first use.
        """
        if brand_pk is None:
            return _bad_request(
                "An employee must be created under a brand: POST /brands/<id>/employees"
            )

        brand = BrandRepository().get(brand_pk)
        if brand is None:
            raise exceptions.NotFound(f"Brand {brand_pk} not found")

        body = request.data if isinstance(request.data, dict) else {}
        try:
            name = require_text(pick(body, "name"), "name")
            position_name = require_text(pick(body, "roles", "role", "position"), "roles")
            job_status = require_text(pick(body, "status", default="active"), "status", 50)
        except ParseError as exc:
            return _bad_request(str(exc))

        position = PositionRepository().get_or_create(position_name)
        employee = EmployeeRepository().create(name=name)
        job = JobRepository().create(
            brand_id=brand.id,
            employee_id=employee.id,
            position_id=position.id,
            status=job_status,
        )

        return Response(
            {
                "employee": EmployeeSchema(many=False).dump(employee),
                "job": _job_payload(job),
            },
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, pk:int | None = None, brand_pk:int | None = None) -> Response:
        """Re-assign an employee's job at a brand.

        The URL is authoritative: a ``brand_ID``/``employee_ID`` in the body is
        accepted but ignored, because honouring it would let a PUT to one URL
        silently edit a different row.
        """
        if brand_pk is None or pk is None:
            return _bad_request(
                "An employment must be updated under a brand: "
                "PUT /brands/<id>/employees/<id>"
            )

        job = JobRepository().for_brand_and_employee(brand_pk, pk)
        if job is None:
            raise exceptions.NotFound(f"Employee {pk} has no job at brand {brand_pk}")

        body = request.data if isinstance(request.data, dict) else {}
        changes = {}
        try:
            raw_position = pick(body, "roles", "role", "position")
            if raw_position is not None:
                position_name = require_text(raw_position, "roles")
                changes["position_id"] = PositionRepository().get_or_create(position_name).id
            raw_status = pick(body, "status")
            if raw_status is not None:
                changes["status"] = require_text(raw_status, "status", 50)
        except ParseError as exc:
            return _bad_request(str(exc))

        if not changes:
            return _bad_request("Nothing to update; send 'roles' and/or 'status'")

        job = JobRepository().update(job, **changes)
        return Response(
            {
                "employee": EmployeeSchema(many=False).dump(job.employee),
                "job": _job_payload(job),
            },
            status=status.HTTP_200_OK,
        )


class EmployeeTimeViewSet(viewsets.ViewSet):
    """``/employees/<id>/times`` - when an employee is booked, and when not."""

    def list(self, request, employee_pk:int | None = None) -> Response:
        employee = EmployeeRepository().get(employee_pk)
        if employee is None:
            raise exceptions.NotFound(f"Employee {employee_pk} not found")

        try:
            modes = parse_modes(request.query_params.get("mode"), ("free", "busy"))
        except ParseError as exc:
            return _bad_request(str(exc))

        shifts = ShiftRepository().for_employee(employee.id)

        payload = {"employee_id": employee.id}
        if "busy" in modes:
            payload["busy"] = [self._busy_block(shift) for shift in shifts]
        if "free" in modes:
            payload["free"] = self._free(shifts)
        return Response(payload, status=status.HTTP_200_OK)

    @staticmethod
    def _busy_block(shift) -> dict:
        role = shift.role
        schedule = role.schedule if role is not None else None
        brand = schedule.brand if schedule is not None else None
        return {
            "shift_id": shift.id,
            "date": shift.date.isoformat() if shift.date else None,
            "starting_time": shift.starting_time.isoformat(),
            "finishing_time": shift.finishing_time.isoformat(),
            "role": role.name if role is not None else None,
            "brand": brand.name if brand is not None else None,
        }

    @staticmethod
    def _free(shifts) -> list[dict]:
        """The complement of the busy blocks, day by day.

        Only days the employee already works are reported - a day with no shift
        at all is free by definition, and listing every such day would be an
        unbounded answer.
        """
        by_day: dict[object, list] = {}
        for shift in shifts:
            by_day.setdefault(shift.date, []).append(shift)

        free: list[dict] = []
        for day in sorted(by_day):
            blocks = sorted(
                by_day[day], key=lambda s: (s.starting_time, s.finishing_time)
            )
            cursor = WORKDAY_START
            for block in blocks:
                if block.starting_time > cursor:
                    free.append(
                        {
                            "date": day.isoformat() if day else None,
                            "starting_time": cursor.isoformat(),
                            "finishing_time": block.starting_time.isoformat(),
                        }
                    )
                # Overlapping shifts must not rewind cursor.
                if block.finishing_time > cursor:
                    cursor = block.finishing_time
            if cursor < WORKDAY_END:
                free.append(
                    {
                        "date": day.isoformat() if day else None,
                        "starting_time": cursor.isoformat(),
                        "finishing_time": WORKDAY_END.isoformat(),
                    }
                )
        return free


class BrandViewSet(viewsets.ViewSet):
    def retrieve(self, request, pk:int) -> Response:
        brand = BrandRepository().get(pk)
        if brand is None:
            raise exceptions.NotFound("Brand not found")
        return Response(BrandSchema(many = False).dump(brand), status=status.HTTP_200_OK)

    def list(self, request):
        """Every brand. An empty result is an empty list, not a 404."""
        brands = BrandRepository().list()
        return Response(BrandSchema(many = True).dump(brands), status=status.HTTP_200_OK)

    def create(self, request) -> Response:
        body = request.data if isinstance(request.data, dict) else {}
        try:
            name = require_text(pick(body, "name"), "name")
            raw_location = pick(body, "location")
            location = (
                require_text(raw_location, "location", 255)
                if raw_location is not None
                else None
            )
        except ParseError as exc:
            return _bad_request(str(exc))

        brand = BrandRepository().create(name=name, location=location)
        return Response(
            BrandSchema(many=False).dump(brand), status=status.HTTP_201_CREATED
        )


class ScheduleViewSet(viewsets.ViewSet):
    def retrieve(self, request, pk:int | None = None, brand_pk:int | None = None) -> Response:
        schedules = ScheduleRepository()
        schedule = (
            schedules.get(pk)
            if brand_pk is None
            else schedules.schedule_for_brand(brand_pk, pk)
        )
        if schedule is None:
            raise exceptions.NotFound("Schedule not found")
        return Response(
            ScheduleSchema(many=False).dump(schedule), status=status.HTTP_200_OK
        )

    def list(self, request, brand_pk:int | None = None) -> Response:
        schedules = ScheduleRepository()
        rows = schedules.list() if brand_pk is None else schedules.for_brand(brand_pk)
        return Response(ScheduleSchema(many=True).dump(rows), status=status.HTTP_200_OK)

    def create(self, request, brand_pk:int | None = None) -> Response:
        if brand_pk is None:
            return _bad_request(
                "A schedule must be created under a brand: POST /brands/<id>/schedules"
            )

        brand = BrandRepository().get(brand_pk)
        if brand is None:
            raise exceptions.NotFound(f"Brand {brand_pk} not found")

        body = request.data if isinstance(request.data, dict) else {}
        try:
            starting_date = parse_date(
                pick(body, "starting_date", "date"), "starting_date"
            )
            raw_created_by = pick(body, "created_by")
            created_by = (
                parse_int(raw_created_by, "created_by")
                if raw_created_by is not None
                else None
            )
        except ParseError as exc:
            return _bad_request(str(exc))

        schedule = ScheduleRepository().create(
            brand_id=brand.id, starting_date=starting_date, created_by=created_by
        )
        return Response(
            ScheduleSchema(many=False).dump(schedule), status=status.HTTP_201_CREATED
        )


class RoleViewSet(viewsets.ViewSet):
    def retrieve(self, request, pk:int | None = None, schedule_pk:int | None = None) -> Response:
        roles = RoleRepository()
        role = (
            roles.get(pk)
            if schedule_pk is None
            else roles.role_for_schedule(schedule_pk, pk)
        )
        if role is None:
            raise exceptions.NotFound("Role not found")
        return Response(RoleSchema(many=False).dump(role), status=status.HTTP_200_OK)

    def list(self, request, schedule_pk:int | None = None) -> Response:
        roles = RoleRepository()
        rows = roles.list() if schedule_pk is None else roles.for_schedule(schedule_pk)
        return Response(RoleSchema(many=True).dump(rows), status=status.HTTP_200_OK)

    def create(self, request, schedule_pk:int | None = None) -> Response:
        """Add a role to a schedule.

        ``Role.schedule_id`` is NOT NULL, so an unnested POST has nowhere to put
        the row. That is answered with a 400 pointing at the nested URL rather
        than inventing a default schedule.
        """
        if schedule_pk is None:
            return _bad_request(
                "A role belongs to a schedule and cannot be created on its own; "
                "POST /api/v1/schedules/<schedule_id>/roles instead"
            )

        schedule = ScheduleRepository().get(schedule_pk)
        if schedule is None:
            raise exceptions.NotFound(f"Schedule {schedule_pk} not found")

        body = request.data if isinstance(request.data, dict) else {}
        try:
            name = require_text(pick(body, "name"), "name")
        except ParseError as exc:
            return _bad_request(str(exc))

        role = RoleRepository().create(name=name, schedule_id=schedule.id)
        return Response(RoleSchema(many=False).dump(role), status=status.HTTP_201_CREATED)


class ShiftViewSet(viewsets.ViewSet):
    """Shifts, reachable under a role, a schedule, or an employee.

    Which parent is present decides what a verb means: ``create`` and the
    collection-level ``update`` need a role, while the schedule- and
    employee-nested mounts are read-only listings.
    """

    def list(
        self,
        request,
        role_pk:int | None = None,
        schedule_pk:int | None = None,
        employee_pk:int | None = None,
    ) -> Response:
        shifts = ShiftRepository()
        if employee_pk is not None and schedule_pk is not None:
            rows = shifts.for_employee_in_schedule(employee_pk, schedule_pk)
        elif employee_pk is not None:
            rows = shifts.for_employee(employee_pk)
        elif role_pk is not None:
            rows = shifts.for_role(role_pk)
        elif schedule_pk is not None:
            rows = shifts.for_schedule(schedule_pk)
        else:
            rows = shifts.list()
        return Response([_shift_payload(row) for row in rows], status=status.HTTP_200_OK)

    def retrieve(
        self,
        request,
        pk:int | None = None,
        role_pk:int | None = None,
        schedule_pk:int | None = None,
        employee_pk:int | None = None,
    ) -> Response:
        """One shift, scoped to whichever parents the URL names.

        A shift reached through the wrong role, schedule or employee is a 404
        rather than a 200: the URL asserts where the row lives, and answering
        with a shift from somewhere else would make the nesting a lie. The
        parents are read off the row's own relationships, so this costs no
        extra query.
        """
        shift = ShiftRepository().get(pk)
        if shift is None:
            raise exceptions.NotFound("Shift not found")

        role = shift.role
        schedule = role.schedule if role is not None else None
        job = shift.job
        mismatched = (
            (role_pk is not None and str(shift.role_id) != str(role_pk))
            or (
                schedule_pk is not None
                and (schedule is None or str(schedule.id) != str(schedule_pk))
            )
            or (
                employee_pk is not None
                and (job is None or str(job.employee_id) != str(employee_pk))
            )
        )
        if mismatched:
            raise exceptions.NotFound(f"Shift {pk} not found here")
        return Response(_shift_payload(shift), status=status.HTTP_200_OK)

    def create(
        self, request, schedule_pk:int | None = None, role_pk:int | None = None
    ) -> Response:
        role, error = self._role(schedule_pk, role_pk)
        if error is not None:
            return error

        body = request.data if isinstance(request.data, dict) else {}
        try:
            fields = self._times(body)
            job, message = _resolve_job(role, body)
        except ParseError as exc:
            return _bad_request(str(exc))
        if job is None:
            return _bad_request(message)

        shift = ShiftRepository().create(job_id=job.id, role_id=role.id, **fields)
        return Response(_shift_payload(shift), status=status.HTTP_201_CREATED)

    def update(
        self,
        request,
        schedule_pk:int | None = None,
        role_pk:int | None = None,
        employee_pk:int | None = None,
    ) -> Response:
        """Collection-level PUT: upsert the shift for (role, employee, date).

        There is no shift pk in the URL, so the triple identifies the row. An
        existing shift on that day has its times replaced; otherwise one is
        created, and the status code says which happened.

        ``employee_pk`` is accepted only because the router adds PUT to every
        list route, including the read-only employee mounts. It is never a way
        in: without a role there is nothing to upsert against, so those URLs
        fall through to the 400 from :meth:`_role`.
        """
        role, error = self._role(schedule_pk, role_pk)
        if error is not None:
            return error

        body = request.data if isinstance(request.data, dict) else {}
        try:
            fields = self._times(body)
            job, message = _resolve_job(role, body)
        except ParseError as exc:
            return _bad_request(str(exc))
        if job is None:
            return _bad_request(message)

        shifts = ShiftRepository()
        existing = shifts.for_role_job_date(role.id, job.id, fields["date"])
        if existing is not None:
            shift = shifts.update(
                existing,
                starting_time=fields["starting_time"],
                finishing_time=fields["finishing_time"],
            )
            return Response(_shift_payload(shift), status=status.HTTP_200_OK)

        shift = shifts.create(job_id=job.id, role_id=role.id, **fields)
        return Response(_shift_payload(shift), status=status.HTTP_201_CREATED)

    @staticmethod
    def _role(schedule_pk, role_pk):
        """Load the role, insisting it really sits under the schedule in the URL."""
        if role_pk is None:
            return None, _bad_request(
                "A shift must be posted under a role: "
                "/api/v1/schedules/<schedule_id>/roles/<role_id>/shifts"
            )
        roles = RoleRepository()
        role = (
            roles.get(role_pk)
            if schedule_pk is None
            else roles.role_for_schedule(schedule_pk, role_pk)
        )
        if role is None:
            raise exceptions.NotFound(
                f"Role {role_pk} not found in schedule {schedule_pk}"
            )
        return role, None

    @staticmethod
    def _times(body: dict) -> dict:
        """The three time columns, parsed. ``starting_date`` maps to ``date``."""
        starting = parse_time(pick(body, "starting_time", "start_time"), "starting_time")
        finishing = parse_time(
            pick(body, "finishing_time", "finish_time", "ending_time"), "finishing_time"
        )
        if finishing <= starting:
            raise ParseError("finishing_time must be after starting_time")
        on_date = parse_date(pick(body, "starting_date", "date"), "starting_date")
        return {
            "starting_time": starting,
            "finishing_time": finishing,
            "date": on_date,
        }
