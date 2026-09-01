"""Consistent test/demo data for the scheduling domain.

``mysite/`` is the Python import root, so run this with ``mysite`` as the
working directory (imports here are ``database.engine`` / ``database.models``)::

    cd mysite
    ..\\.venv\\Scripts\\python.exe -m database.seed_data            # seed + validate
    ..\\.venv\\Scripts\\python.exe -m database.seed_data --validate # validate only
    ..\\.venv\\Scripts\\python.exe -m database.seed_data --clear    # delete seeded rows
    ..\\.venv\\Scripts\\python.exe -m database.seed_data --reset    # clear, then seed

Importing this module opens a DB connection (``database.engine`` does that as a
side effect). It never creates or drops tables -- run
``python manage.py init_db`` first if the schema is not there yet.

The data satisfies five invariants, all re-checked by :func:`validate`:

1. ``shift.role.schedule`` is the schedule the shift belongs to.
2. The shift's job is at the schedule's brand, and that job's position name
    equals the shift's role name.
3. (1) + (2): an employee is only schedulable on a shift when he holds a job at
    the brand owning the schedule *and* his position matches the role.
4. No employee has two shifts whose ``[starting_time, finishing_time)``
    intervals overlap on the same date -- checked across every brand and
    schedule, since an employee may hold jobs at more than one brand.
5. ``shift.date`` falls inside ``[schedule.starting_date, +6 days]``, and every
    ``starting_date`` is a Monday.
"""
from __future__ import annotations

from datetime import date, time, timedelta

from sqlalchemy.orm import Session, joinedload

from database.engine import session as default_session
from database.models import (
    Brand,
    Employee,
    Job,
    Position,
    Role,
    Schedule,
    Shift,
)

# --------------------------------------------------------------- declarative data

#: Monday. Every schedule's ``starting_date`` is this or a later Monday.
WEEK_1 = date(2026, 9, 7)
WEEK_2 = WEEK_1 + timedelta(days=7)

POSITIONS: tuple[str, ...] = ("Cashier", "Cook", "Server", "Barista", "Manager")

#: (brand key, name, location)
BRANDS: tuple[tuple[str, str, str], ...] = (
    ("bean", "Bean & Board", "12 Nile St, Cairo"),
    ("grill", "Grill House", "44 Corniche, Alexandria"),
    ("noodle", "Noodle Lab", "8 Tahrir Sq, Giza"),
)

EMPLOYEES: tuple[str, ...] = (
    "Amina Hassan",
    "Bilal Farouk",
    "Carla Mendes",
    "Dina Salah",
    "Emad Nabil",
    "Farah Zaki",
    "Gamal Rashad",
    "Hana Youssef",
    "Ismail Adel",
    "Jana Kamal",
    "Karim Louis",
    "Layla Morsi",
)

#: (employee name, brand key, position name, status). Employees appearing twice
#: hold jobs at two brands -- the cross-brand overlap case invariant 4 guards.
JOBS: tuple[tuple[str, str, str, str], ...] = (
    # Bean & Board -- cafe
    ("Amina Hassan", "bean", "Manager", "active"),
    ("Bilal Farouk", "bean", "Barista", "active"),
    ("Carla Mendes", "bean", "Barista", "active"),
    ("Dina Salah", "bean", "Cashier", "active"),
    ("Emad Nabil", "bean", "Server", "active"),
    # Grill House -- restaurant
    ("Farah Zaki", "grill", "Manager", "active"),
    ("Gamal Rashad", "grill", "Cook", "active"),
    ("Hana Youssef", "grill", "Cook", "active"),
    ("Ismail Adel", "grill", "Server", "active"),
    ("Dina Salah", "grill", "Cashier", "active"),  # second brand
    # Noodle Lab
    ("Jana Kamal", "noodle", "Manager", "active"),
    ("Karim Louis", "noodle", "Cook", "active"),
    ("Layla Morsi", "noodle", "Server", "active"),
    ("Emad Nabil", "noodle", "Server", "active"),  # second brand
    ("Bilal Farouk", "noodle", "Cashier", "active"),  # second brand
)

#: (schedule key, brand key, starting Monday, creator employee name)
SCHEDULES: tuple[tuple[str, str, date, str], ...] = (
    ("bean-w1", "bean", WEEK_1, "Amina Hassan"),
    ("bean-w2", "bean", WEEK_2, "Amina Hassan"),
    ("grill-w1", "grill", WEEK_1, "Farah Zaki"),
    ("noodle-w1", "noodle", WEEK_1, "Jana Kamal"),
)

#: schedule key -> role names. Only positions actually staffed at that brand.
ROLES: dict[str, tuple[str, ...]] = {
    "bean-w1": ("Manager", "Barista", "Cashier", "Server"),
    "bean-w2": ("Manager", "Barista", "Cashier"),
    "grill-w1": ("Manager", "Cook", "Server", "Cashier"),
    "noodle-w1": ("Manager", "Cook", "Server", "Cashier"),
}

MORNING = (time(8, 0), time(16, 0))
EVENING = (time(16, 0), time(23, 0))
MIDDAY = (time(11, 0), time(15, 0))
LATE = (time(17, 0), time(22, 0))

#: (schedule key, day offset from starting_date 0-6, employee name, role name,
#:  (starting_time, finishing_time))
SHIFTS: tuple[tuple[str, int, str, str, tuple[time, time]], ...] = (
    # ---- Bean & Board, week 1
    ("bean-w1", 0, "Amina Hassan", "Manager", MORNING),
    ("bean-w1", 0, "Bilal Farouk", "Barista", MORNING),
    ("bean-w1", 0, "Carla Mendes", "Barista", EVENING),
    ("bean-w1", 0, "Dina Salah", "Cashier", MORNING),
    ("bean-w1", 1, "Amina Hassan", "Manager", MORNING),
    ("bean-w1", 1, "Carla Mendes", "Barista", MORNING),
    ("bean-w1", 1, "Emad Nabil", "Server", EVENING),
    ("bean-w1", 2, "Bilal Farouk", "Barista", MORNING),
    ("bean-w1", 2, "Dina Salah", "Cashier", EVENING),
    ("bean-w1", 3, "Amina Hassan", "Manager", MIDDAY),
    ("bean-w1", 3, "Carla Mendes", "Barista", MORNING),
    ("bean-w1", 4, "Bilal Farouk", "Barista", MORNING),
    ("bean-w1", 4, "Emad Nabil", "Server", MIDDAY),
    ("bean-w1", 5, "Carla Mendes", "Barista", EVENING),
    ("bean-w1", 5, "Dina Salah", "Cashier", MORNING),
    ("bean-w1", 6, "Amina Hassan", "Manager", MORNING),
    ("bean-w1", 6, "Bilal Farouk", "Barista", EVENING),
    # ---- Bean & Board, week 2
    ("bean-w2", 0, "Amina Hassan", "Manager", MORNING),
    ("bean-w2", 0, "Carla Mendes", "Barista", MORNING),
    ("bean-w2", 1, "Bilal Farouk", "Barista", MORNING),
    ("bean-w2", 1, "Dina Salah", "Cashier", EVENING),
    ("bean-w2", 2, "Carla Mendes", "Barista", EVENING),
    ("bean-w2", 3, "Amina Hassan", "Manager", MIDDAY),
    ("bean-w2", 4, "Bilal Farouk", "Barista", MORNING),
    ("bean-w2", 5, "Dina Salah", "Cashier", MORNING),
    # ---- Grill House, week 1
    ("grill-w1", 0, "Farah Zaki", "Manager", MORNING),
    ("grill-w1", 0, "Gamal Rashad", "Cook", MORNING),
    ("grill-w1", 0, "Hana Youssef", "Cook", EVENING),
    ("grill-w1", 0, "Ismail Adel", "Server", EVENING),
    # Dina works Cashier at the cafe in the morning and here in the evening --
    # two brands, same day, non-overlapping.
    ("grill-w1", 0, "Dina Salah", "Cashier", EVENING),
    ("grill-w1", 1, "Farah Zaki", "Manager", MORNING),
    ("grill-w1", 1, "Gamal Rashad", "Cook", EVENING),
    ("grill-w1", 2, "Hana Youssef", "Cook", MORNING),
    ("grill-w1", 2, "Ismail Adel", "Server", MIDDAY),
    ("grill-w1", 3, "Farah Zaki", "Manager", MORNING),
    ("grill-w1", 3, "Gamal Rashad", "Cook", EVENING),
    ("grill-w1", 4, "Hana Youssef", "Cook", MORNING),
    ("grill-w1", 4, "Dina Salah", "Cashier", EVENING),
    ("grill-w1", 5, "Ismail Adel", "Server", EVENING),
    ("grill-w1", 6, "Farah Zaki", "Manager", MIDDAY),
    ("grill-w1", 6, "Gamal Rashad", "Cook", MORNING),
    # ---- Noodle Lab, week 1
    ("noodle-w1", 0, "Jana Kamal", "Manager", MORNING),
    ("noodle-w1", 0, "Karim Louis", "Cook", MORNING),
    ("noodle-w1", 0, "Layla Morsi", "Server", EVENING),
    ("noodle-w1", 1, "Jana Kamal", "Manager", MORNING),
    ("noodle-w1", 1, "Karim Louis", "Cook", EVENING),
    # Emad's only other week-1 shifts are at the cafe on days 1 and 4, neither
    # of which collides with this midday slot on day 2.
    ("noodle-w1", 2, "Emad Nabil", "Server", MIDDAY),
    ("noodle-w1", 2, "Bilal Farouk", "Cashier", EVENING),
    ("noodle-w1", 3, "Jana Kamal", "Manager", LATE),
    ("noodle-w1", 3, "Karim Louis", "Cook", MORNING),
    ("noodle-w1", 4, "Layla Morsi", "Server", MORNING),
    ("noodle-w1", 4, "Bilal Farouk", "Cashier", LATE),
    ("noodle-w1", 5, "Jana Kamal", "Manager", MORNING),
    ("noodle-w1", 5, "Karim Louis", "Cook", EVENING),
    ("noodle-w1", 6, "Layla Morsi", "Server", MIDDAY),
    ("noodle-w1", 6, "Emad Nabil", "Server", EVENING),
)


class SeedError(RuntimeError):
    """Raised when the seed data itself is inconsistent."""


class ValidationError(RuntimeError):
    """Raised by :func:`validate` when the DB violates an invariant."""

    def __init__(self, violations: list[str]) -> None:
        super().__init__(
            f"{len(violations)} invariant violation(s):\n  "
            + "\n  ".join(violations)
        )
        self.violations = violations


def _resolve(session: Session | None) -> Session:
    """Session convention: injected session, else the shared scoped session."""
    return session if session is not None else default_session


# ------------------------------------------------------------------------ seed


def seed(session: Session | None = None, *, force: bool = False) -> dict[str, int]:
    """Insert the demo data and commit. Returns per-table row counts.

    Skips entirely (returning zero counts) when any brand, employee, or shift
    already exists, unless ``force=True``. Never creates or drops tables.
    """
    session = _resolve(session)

    if not force and _has_data(session):
        return {k: 0 for k in
                ("brands", "positions", "employees", "jobs", "schedules", "roles", "shifts")}

    try:
        positions = {name: Position(name=name) for name in POSITIONS}
        session.add_all(positions.values())

        brands = {key: Brand(name=name, location=loc) for key, name, loc in BRANDS}
        session.add_all(brands.values())

        employees = {name: Employee(name=name) for name in EMPLOYEES}
        session.add_all(employees.values())

        # (employee name, brand key) -> Job. This mapping is what makes
        # invariants 2 and 3 hold: a shift can only be built from a job that
        # already ties the employee to the brand and the position.
        jobs: dict[tuple[str, str], Job] = {}
        for emp_name, brand_key, position_name, status in JOBS:
            if (emp_name, brand_key) in jobs:
                raise SeedError(f"duplicate job for {emp_name!r} at {brand_key!r}")
            job = Job(
                brand=brands[brand_key],
                employee=employees[emp_name],
                position=positions[position_name],
                status=status,
            )
            jobs[(emp_name, brand_key)] = job
        session.add_all(jobs.values())

        schedules: dict[str, Schedule] = {}
        schedule_brand: dict[str, str] = {}
        for sched_key, brand_key, starting_date, creator in SCHEDULES:
            if starting_date.weekday() != 0:
                raise SeedError(
                    f"schedule {sched_key!r} starting_date {starting_date} is not a Monday"
                )
            schedules[sched_key] = Schedule(
                brand=brands[brand_key],
                starting_date=starting_date,
                creator=employees[creator],
            )
            schedule_brand[sched_key] = brand_key
        session.add_all(schedules.values())

        # (schedule key, role name) -> Role. Roles are per-schedule, so a shift
        # picking a role from its own schedule is what invariant 1 requires.
        roles: dict[tuple[str, str], Role] = {}
        for sched_key, role_names in ROLES.items():
            if sched_key not in schedules:
                raise SeedError(f"roles declared for unknown schedule {sched_key!r}")
            for role_name in role_names:
                if (sched_key, role_name) in roles:
                    raise SeedError(
                        f"duplicate role {role_name!r} on schedule {sched_key!r}"
                    )
                roles[(sched_key, role_name)] = Role(
                    name=role_name, schedule=schedules[sched_key]
                )
        session.add_all(roles.values())

        shifts: list[Shift] = []
        # employee name -> list of (date, start, finish), for the overlap check
        booked: dict[str, list[tuple[date, time, time]]] = {}
        for sched_key, day_offset, emp_name, role_name, (start, finish) in SHIFTS:
            if not 0 <= day_offset <= 6:
                raise SeedError(f"day offset {day_offset} outside the schedule week")
            if start >= finish:
                raise SeedError(f"shift for {emp_name!r} starts at or after it finishes")

            brand_key = schedule_brand[sched_key]
            job = jobs.get((emp_name, brand_key))
            if job is None:
                raise SeedError(
                    f"{emp_name!r} has no job at brand {brand_key!r} "
                    f"(schedule {sched_key!r})"
                )
            if job.position.name != role_name:
                raise SeedError(
                    f"{emp_name!r} is {job.position.name!r} at {brand_key!r}, "
                    f"cannot fill role {role_name!r}"
                )
            role = roles.get((sched_key, role_name))
            if role is None:
                raise SeedError(
                    f"schedule {sched_key!r} has no role {role_name!r}"
                )

            shift_date = schedules[sched_key].starting_date + timedelta(days=day_offset)
            for other_date, other_start, other_finish in booked.setdefault(emp_name, []):
                if other_date == shift_date and start < other_finish and other_start < finish:
                    raise SeedError(
                        f"{emp_name!r} double-booked on {shift_date}: "
                        f"{start}-{finish} overlaps {other_start}-{other_finish}"
                    )
            booked[emp_name].append((shift_date, start, finish))

            shifts.append(
                Shift(
                    job=job,
                    role=role,
                    starting_time=start,
                    finishing_time=finish,
                    date=shift_date,
                )
            )
        session.add_all(shifts)

        session.commit()
    except Exception:
        session.rollback()
        raise

    return {
        "brands": len(brands),
        "positions": len(positions),
        "employees": len(employees),
        "jobs": len(jobs),
        "schedules": len(schedules),
        "roles": len(roles),
        "shifts": len(shifts),
    }


def _has_data(session: Session) -> bool:
    """True if any table :func:`seed` writes to already holds a row.

    Every seeded table is checked, not just a representative few: none of
    ``Brand``/``Employee``/``Position`` has a unique constraint on its name, so
    seeding on top of a partially-populated database would silently duplicate
    rows rather than fail.
    """
    for model in (Brand, Position, Employee, Job, Schedule, Role, Shift):
        if session.query(model).first() is not None:
            return True
    return False


# ----------------------------------------------------------------------- clear


def clear(session: Session | None = None) -> dict[str, int]:
    """Delete the scheduling rows, child-first. Does NOT drop tables.

    Leaves ``managers`` and ``refresh_tokens`` alone -- auth data is unrelated
    to the demo scheduling data.
    """
    session = _resolve(session)
    deleted: dict[str, int] = {}
    try:
        for model in (Shift, Role, Schedule, Job, Employee, Brand, Position):
            deleted[model.__tablename__] = (
                session.query(model).delete(synchronize_session=False)
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return deleted


# -------------------------------------------------------------------- validate


def validate(session: Session | None = None, *, raise_on_violation: bool = True) -> list[str]:
    """Re-check all five invariants against the database.

    Returns the list of violation messages (empty when the data is consistent).
    Raises :class:`ValidationError` on any violation unless
    ``raise_on_violation=False``.
    """
    session = _resolve(session)
    violations: list[str] = []

    shifts = (
        session.query(Shift)
        .options(
            joinedload(Shift.role).joinedload(Role.schedule),
            joinedload(Shift.job).joinedload(Job.position),
            joinedload(Shift.job).joinedload(Job.employee),
        )
        .all()
    )

    # brand id -> its schedules, so a shift's own schedule can be identified
    # without relying on the role it points at (see invariant 1 below).
    schedules_by_brand: dict[int, list[Schedule]] = {}

    # Invariant 5b: every schedule starts on a Monday.
    for schedule in session.query(Schedule).all():
        schedules_by_brand.setdefault(schedule.brand_id, []).append(schedule)
        if schedule.starting_date.weekday() != 0:
            violations.append(
                f"schedule {schedule.id}: starting_date {schedule.starting_date} "
                f"is a {schedule.starting_date.strftime('%A')}, not a Monday"
            )

    # A brand must not have two schedules covering the same week. This is its
    # own root cause, reported separately: invariant 1 identifies a shift's
    # schedule by "the schedule of the job's brand whose week contains the
    # date", which is only well defined when brand weeks are disjoint. Without
    # this check, one duplicate schedule would surface as an "ambiguous"
    # violation on every shift in that week instead of being named directly.
    for brand_id, brand_schedules in schedules_by_brand.items():
        ordered = sorted(brand_schedules, key=lambda sc: sc.starting_date)
        for earlier, later in zip(ordered, ordered[1:]):
            if later.starting_date <= earlier.starting_date + timedelta(days=6):
                violations.append(
                    f"brand {brand_id}: schedules {earlier.id} "
                    f"({earlier.starting_date}) and {later.id} "
                    f"({later.starting_date}) cover overlapping weeks"
                )

    # employee id -> list of (date, start, finish, shift id), for invariant 4
    by_employee: dict[int, list[tuple[date, time, time, int]]] = {}

    for shift in shifts:
        role = shift.role
        job = shift.job
        if role is None or job is None:
            violations.append(f"shift {shift.id}: missing role or job row")
            continue
        schedule = role.schedule
        if schedule is None:
            violations.append(f"shift {shift.id}: role {role.id} has no schedule")
            continue

        # Invariant 1 -- shift.role.schedule is *the* schedule being populated.
        # A shift has no direct schedule FK, so the schedule it belongs to is
        # determined independently: it is the unique schedule of the job's brand
        # whose week contains shift.date. The role's schedule must be that one.
        expected = [
            sched for sched in schedules_by_brand.get(job.brand_id, ())
            if sched.starting_date <= shift.date <= sched.starting_date + timedelta(days=6)
        ]
        if not expected:
            violations.append(
                f"shift {shift.id}: no schedule at brand {job.brand_id} covers "
                f"date {shift.date} (invariant 1)"
            )
        elif len(expected) > 1:
            violations.append(
                f"shift {shift.id}: date {shift.date} is covered by "
                f"{len(expected)} schedules at brand {job.brand_id}, so the "
                f"shift's own schedule is ambiguous (invariant 1)"
            )
        elif expected[0].id != schedule.id:
            violations.append(
                f"shift {shift.id}: role {role.id} belongs to schedule "
                f"{schedule.id}, but the shift sits in schedule "
                f"{expected[0].id} (invariant 1)"
            )
        if role.schedule_id != schedule.id:
            violations.append(
                f"shift {shift.id}: role {role.id} schedule_id {role.schedule_id} "
                f"!= schedule {schedule.id}"
            )

        # Invariant 2/3 -- job at the schedule's brand, position matches role.
        if job.brand_id != schedule.brand_id:
            violations.append(
                f"shift {shift.id}: job {job.id} is at brand {job.brand_id} but "
                f"schedule {schedule.id} belongs to brand {schedule.brand_id} "
                f"(invariant 2)"
            )
        if job.position is None or job.position.name != role.name:
            got = job.position.name if job.position else None
            violations.append(
                f"shift {shift.id}: job {job.id} position {got!r} != role "
                f"{role.name!r} (invariant 3)"
            )

        # Invariant 5a -- date inside the schedule's week.
        week_end = schedule.starting_date + timedelta(days=6)
        if not (schedule.starting_date <= shift.date <= week_end):
            violations.append(
                f"shift {shift.id}: date {shift.date} outside schedule "
                f"{schedule.id} week [{schedule.starting_date}, {week_end}] "
                f"(invariant 5)"
            )

        if shift.starting_time >= shift.finishing_time:
            violations.append(
                f"shift {shift.id}: starting_time {shift.starting_time} >= "
                f"finishing_time {shift.finishing_time}"
            )

        by_employee.setdefault(job.employee_id, []).append(
            (shift.date, shift.starting_time, shift.finishing_time, shift.id)
        )

    # Invariant 4 -- no overlap for one employee, across all brands/schedules.
    # Comparing only adjacent pairs after sorting is NOT enough: a long shift
    # can contain a later short one with an unrelated shift sorted between them,
    # and the containment would go unreported. Sorting by start time and
    # carrying the furthest finish seen so far on that date catches every
    # overlap, including containment.
    for employee_id, entries in by_employee.items():
        entries.sort(key=lambda e: (e[0], e[1], e[2]))
        open_date: date | None = None
        max_finish: time | None = None
        max_finish_id: int | None = None
        max_finish_start: time | None = None
        for c_date, c_start, c_finish, c_id in entries:
            if c_date != open_date:
                open_date, max_finish = c_date, c_finish
                max_finish_id, max_finish_start = c_id, c_start
                continue
            if c_start < max_finish:
                violations.append(
                    f"employee {employee_id}: shift {max_finish_id} "
                    f"({open_date} {max_finish_start}-{max_finish}) overlaps "
                    f"shift {c_id} ({c_date} {c_start}-{c_finish}) "
                    f"(invariant 4)"
                )
            if c_finish > max_finish:
                max_finish = c_finish
                max_finish_id, max_finish_start = c_id, c_start

    if violations and raise_on_violation:
        raise ValidationError(violations)
    return violations


# ------------------------------------------------------------------------ main


def _summary(session: Session) -> str:
    rows = [
        (model.__tablename__, session.query(model).count())
        for model in (Brand, Position, Employee, Job, Schedule, Role, Shift)
    ]
    return ", ".join(f"{name}={count}" for name, count in rows)


def main(argv: list[str] | None = None) -> int:
    import sys

    argv = sys.argv[1:] if argv is None else argv
    do_clear = "--clear" in argv or "--reset" in argv
    do_seed = "--validate" not in argv and "--clear" not in argv
    force = "--force" in argv or "--reset" in argv

    if do_clear:
        print(f"clear(): {clear()}")

    if do_seed:
        counts = seed(force=force)
        if any(counts.values()):
            print(f"seed(): inserted {counts}")
        else:
            print("seed(): skipped, data already present (use --force or --reset)")

    print(f"db contents: {_summary(default_session)}")
    violations = validate(raise_on_violation=False)
    if violations:
        print(f"validate(): FAILED with {len(violations)} violation(s)")
        for line in violations:
            print(f"  - {line}")
        return 1
    print("validate(): OK - all 5 invariants hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
