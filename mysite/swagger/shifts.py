"""Schema for ``ShiftViewSet`` - the richest contract in the API.

Contract read off ``components/shift.py``. A shift is created empty and staffed
later, so the two writes are genuinely different operations sharing a payload
vocabulary:

**POST** creates an *unstaffed* slot. ``date``, ``starting_time`` and
``finishing_time`` are all required, the span must be non-empty, and ``date``
must fall inside the week its schedule covers - ``[starting_date, +6 days]``,
anchored to that schedule's own start day, whatever weekday that is. A body
carrying ``employee_id`` or ``job_id`` is **rejected** with a 400 rather than
ignored - a caller sending one plainly expects a staffed shift back, and a 201
with ``employee_id: null`` would look like a bug.

**PUT** retimes a shift, staffs it, or unstaffs it. The three time fields are
optional *here*, but ``_times`` parses them as a set: mention any one and the
complete valid triple must be present, so a partial triple is a 400 rather than
a half-moved shift - and the new ``date`` is held to the schedule week just as
POST is. A body that leaves the times alone is not week-checked, so a pure
re-assignment never fails on a date it did not send. Staffing then runs four eligibility rules - the job must
belong to the role's brand, its position name must equal the role's name, it
must be ``active``, and the employee must be free across every job they hold.

The staffing keys are the subtle part, and ``_staffing_intent`` is precise
about it: every present key null means unstaff, every one non-null means staff,
and a *mix* is a 400 ("Contradictory staffing") rather than a guess. Omitting
them entirely leaves the assignment alone. Sending neither key on a PUT that
does staff is also legal - the role's own name is then read as a position name,
which resolves only if exactly one active employee holds it in the brand.

Both writes are addressed under a role, and the whole schedule subtree hangs
off a brand - there is no ``/api/v1/schedules/...`` path, and no schedule-level
shift mount either: a shift belongs to a role, so a schedule alone never
addresses one.

There are two mounts:
``brands/{brand_pk}/schedules/{schedule_pk}/roles/{role_pk}/shifts[/{id}]``,
the only writable one, and ``employees/{employee_pk}/shifts[/{id}]``, the
person's own calendar. The employee mount is read-only: its ``POST`` and ``PUT``
are excluded at the router (see ``mysite.urls``), so they are a 405 rather than
a write against a URL that names no role. It also carries neither ``brand_pk``
nor ``schedule_pk``, which is why both are declared on the shared method and
then filtered per-path by ``PathParameterSchema``.
"""
from __future__ import annotations

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers

from swagger.common import (
    BRAND_PK,
    EMPLOYEE_PK,
    ID,
    ROLE_PK,
    SCHEDULE_PK,
    bad_request,
    not_found,
    shape,
)

# Flattens a walk across five tables, matching ``components.payloads``.
ShiftResponse, ShiftListResponse = shape(
    "Shift",
    {
        "shift_id": serializers.IntegerField(),
        "job_id": serializers.IntegerField(allow_null=True),
        "employee_id": serializers.IntegerField(allow_null=True),
        "employee": serializers.CharField(allow_null=True),
        "role_id": serializers.IntegerField(),
        "role": serializers.CharField(allow_null=True),
        "schedule_id": serializers.IntegerField(allow_null=True),
        "brand_id": serializers.IntegerField(allow_null=True),
        "brand": serializers.CharField(allow_null=True),
        "date": serializers.DateField(allow_null=True),
        "starting_time": serializers.TimeField(allow_null=True),
        "finishing_time": serializers.TimeField(allow_null=True),
    },
)

_TIME_HELP = "Bare integer hours are accepted, so `8` means 08:00 and `24` means 23:59."

ShiftCreateRequest = inline_serializer(
    name="ShiftCreateRequest",
    fields={
        "date": serializers.CharField(
            help_text=(
                "Required. D/M/YYYY or YYYY-MM-DD. Must fall inside the "
                "schedule's week - `[starting_date, starting_date + 6 days]`, "
                "inclusive. Alias: `starting_date`."
            )
        ),
        "starting_time": serializers.CharField(
            help_text=f"Required. {_TIME_HELP} Alias: `start_time`."
        ),
        "finishing_time": serializers.CharField(
            help_text=(
                f"Required, and must be after `starting_time`. {_TIME_HELP} "
                "Aliases: `finish_time`, `ending_time`."
            )
        ),
    },
)

ShiftUpdateRequest = inline_serializer(
    name="ShiftUpdateRequest",
    fields={
        "date": serializers.CharField(
            required=False,
            help_text=(
                "Optional, but the whole time triple must be valid if any of "
                "the three is sent, and the new date must fall inside the "
                "schedule's week - `[starting_date, starting_date + 6 days]`, "
                "inclusive. Alias: `starting_date`."
            ),
        ),
        "starting_time": serializers.CharField(
            required=False, help_text=f"Optional. {_TIME_HELP} Alias: `start_time`."
        ),
        "finishing_time": serializers.CharField(
            required=False,
            help_text=(
                f"Optional. {_TIME_HELP} Aliases: `finish_time`, `ending_time`."
            ),
        ),
        "employee_id": serializers.IntegerField(
            required=False,
            allow_null=True,
            help_text=(
                "Staffs the shift with this employee's job at the role's brand. "
                "Send explicit `null` to unstaff."
            ),
        ),
        "job_id": serializers.IntegerField(
            required=False,
            allow_null=True,
            help_text=(
                "Staffs the shift with this job directly; takes precedence over "
                "`employee_id`, which must agree if also sent."
            ),
        ),
    },
)

_STAFFING_400 = (
    "Contradictory staffing (some keys null, others not), a partial time "
    "triple, an empty span, a date outside the schedule's week, an ineligible "
    "job, or an overlapping booking."
)


shift_schema = extend_schema_view(
    list=extend_schema(
        summary="List shifts",
        description=(
            "Scoped to whichever parent the URL names, most specific first: an "
            "employee listing is that person's calendar, a role listing is one "
            "slot's history. Those are the only two mounts - there is no "
            "unscoped or schedule-level shift listing."
        ),
        parameters=[BRAND_PK, SCHEDULE_PK, ROLE_PK, EMPLOYEE_PK],
        responses={200: ShiftListResponse},
    ),
    retrieve=extend_schema(
        summary="Retrieve a shift",
        description=(
            "Scoped to whichever parents the URL names. A shift reached through "
            "the wrong role, schedule or employee is a 404, not a 200 - the URL "
            "asserts where the row lives."
        ),
        parameters=[ID, BRAND_PK, SCHEDULE_PK, ROLE_PK, EMPLOYEE_PK],
        responses={
            200: ShiftResponse,
            404: not_found("No such shift, or not under these parents."),
        },
    ),
    create=extend_schema(
        summary="Create an unstaffed shift slot",
        description=(
            "Creates the slot with nobody on it: `POST /api/v1/brands/"
            "{brand_pk}/schedules/{schedule_pk}/roles/{role_pk}/shifts`. "
            "All three time fields are required, and `date` must fall inside "
            "the week the schedule covers - `[starting_date, starting_date + 6 "
            "days]`, inclusive, anchored to that schedule's own start day "
            "whatever weekday it is. Sending `employee_id` or `job_id` is a "
            "400 - staff the slot with a follow-up PUT."
        ),
        parameters=[BRAND_PK, SCHEDULE_PK, ROLE_PK],
        request=ShiftCreateRequest,
        responses={
            201: OpenApiResponse(
                response=ShiftResponse,
                description="Slot created; `job_id` and `employee_id` are null.",
            ),
            400: bad_request(
                "A time field is missing or unparseable, the span is empty, "
                "the date falls outside the schedule's week, "
                "`employee_id`/`job_id` was sent, or no role is in the URL."
            ),
            404: not_found("The role or schedule named in the URL does not exist."),
        },
        examples=[
            OpenApiExample(
                "Integer hours",
                value={"date": "7/9/2026", "starting_time": 8, "finishing_time": 16},
                request_only=True,
            ),
            OpenApiExample(
                "ISO date and HH:MM",
                value={
                    "starting_date": "2026-09-07",
                    "start_time": "08:30",
                    "ending_time": "16:30",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Date outside the schedule week",
                value={
                    "error": (
                        "2026-09-03 is outside the schedule week "
                        "[2026-09-04, 2026-09-10]"
                    )
                },
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Staffing rejected on create",
                value={
                    "error": (
                        "A shift is created unassigned; PUT /api/v1/brands/1/"
                        "schedules/1/roles/1/shifts/<shift_id> to staff it"
                    )
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    update=extend_schema(
        summary="Retime, staff, or unstaff a shift",
        description=(
            "The one write on an existing slot: `PUT /api/v1/brands/{brand_pk}"
            "/schedules/{schedule_pk}/roles/{role_pk}/shifts/{id}`.\n\n"
            "- **Retime**: send the complete time triple. A partial triple is a 400.\n"
            "- **Staff**: send `employee_id` (or `job_id`). Four rules apply - the "
            "job must belong to the role's brand, its position must match the "
            "role's name, it must be `active`, and the employee must be free "
            "across every job they hold.\n"
            "- **Unstaff**: send every staffing key you include as `null`. No "
            "rules apply; taking someone off a shift cannot create a clash.\n"
            "- **Neither key**: the existing assignment is left alone.\n\n"
            "A mix of null and non-null staffing keys is a 400, not a guess. "
            "Retiming and staffing in one call is validated against the new span."
        ),
        parameters=[ID, BRAND_PK, SCHEDULE_PK, ROLE_PK],
        request=ShiftUpdateRequest,
        responses={
            200: OpenApiResponse(response=ShiftResponse, description="The updated shift."),
            400: bad_request(_STAFFING_400),
            404: not_found("No such shift under the role named in the URL."),
        },
        examples=[
            OpenApiExample(
                "Staff by employee",
                value={"employee_id": 1},
                request_only=True,
            ),
            OpenApiExample(
                "Retime and staff at once",
                value={
                    "date": "7/9/2026",
                    "starting_time": 9,
                    "finishing_time": 17,
                    "employee_id": 1,
                },
                request_only=True,
            ),
            OpenApiExample(
                "Unstaff",
                value={"employee_id": None},
                request_only=True,
            ),
            OpenApiExample(
                "Contradictory staffing",
                value={"employee_id": None, "job_id": 7},
                request_only=True,
            ),
            OpenApiExample(
                "Retimed outside the schedule week",
                value={
                    "error": (
                        "2026-09-11 is outside the schedule week "
                        "[2026-09-04, 2026-09-10]"
                    )
                },
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Contradictory staffing rejected",
                value={
                    "error": (
                        "Contradictory staffing: employee_id is null but job_id "
                        "is 7. Send every one of job_id, employee_id as null to "
                        "unstaff this shift, or send only the one that names who "
                        "should work it"
                    )
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
)
