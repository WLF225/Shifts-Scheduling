"""Schema for ``EmployeeViewSet``.

Contract read off ``components/employee.py``, where a person and their
employment are two separate writes because they are two separate facts.

``create`` is one view method serving two genuinely different operations, told
apart by whether the URL names a brand:

* ``POST /api/v1/employees`` (``create_person``) records that someone exists.
  ``name`` is the whole body, and the answer is the bare employee. This is the
  only place an Employee row is created.
* ``POST /api/v1/brands/{brand_pk}/employees`` (``employ``) employs an
  *existing* person, creating **only** the Job. ``employee_id`` names them and
  ``roles`` names the position, created on first use; ``status`` defaults to
  ``"active"``. An unknown ``employee_id`` is a 404, not a silent create. One
  person may hold several jobs at the same brand - Cook and Cashier is a real
  arrangement - so re-employing is a 201, never a conflict. The answer is the
  ``{employee, job}`` envelope, which is what confirms *which* person was
  attached.

Those two differ in request body, response body and failure modes, which is
more than a single ``@extend_schema`` can say - see :func:`swagger.common.by_mount`
for why stacking decorators does not split by path, and what is done instead.

``update`` (``update_employment``) edits the *Job*, never the employee's name,
and it edits exactly one field of it: ``status``. An empty body is a 400, and so
is a body carrying ``roles``/``role``/``position`` - a position cannot be
re-assigned through this endpoint, and quietly ignoring the key would look like
a successful re-assignment that never happened. A ``brand_id``/``employee_id`` in
the body is accepted but ignored, because honouring it would let a PUT to one URL
edit a different row.

It is bound only under a brand, ``PUT /api/v1/brands/{brand_pk}/employees/{id}``.
The top-level ``PUT /api/v1/employees/{id}`` is excluded at the router: editing
employment needs a brand, and that URL names none, so it is a 405.
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

from swagger.common import BRAND_PK, ID, bad_request, by_mount, not_found, shape

EmployeeResponse, EmployeeListResponse = shape(
    "Employee",
    {
        "id": serializers.IntegerField(read_only=True),
        "name": serializers.CharField(),
    },
)

JobResponse = inline_serializer(
    name="Job",
    fields={
        "id": serializers.IntegerField(read_only=True),
        "brand_id": serializers.IntegerField(),
        "employee_id": serializers.IntegerField(),
        "position_id": serializers.IntegerField(),
        "role": serializers.CharField(
            allow_null=True, help_text="The position's name."
        ),
        "status": serializers.CharField(),
    },
)

# Both writes report the pair.
EmploymentResponse = inline_serializer(
    name="Employment",
    fields={"employee": EmployeeResponse, "job": JobResponse},
)

CreatePersonRequest = inline_serializer(
    name="CreatePersonRequest",
    fields={
        "name": serializers.CharField(
            max_length=100, help_text="Required. The whole payload."
        ),
    },
)

EmployRequest = inline_serializer(
    name="EmployRequest",
    fields={
        "employee_id": serializers.IntegerField(
            help_text=(
                "Required. An **existing** employee, created beforehand via "
                "`POST /api/v1/employees`. Alias: `employee`."
            )
        ),
        "roles": serializers.CharField(
            max_length=100,
            help_text=(
                "Required. The position to employ them in, created on first "
                "use. Aliases: `role`, `position`."
            ),
        ),
        "status": serializers.ChoiceField(
            choices=["active", "inactive"],
            required=False,
            help_text="Optional; `active` or `inactive`, defaults to `active`.",
        ),
    },
)

UpdateEmploymentRequest = inline_serializer(
    name="UpdateEmploymentRequest",
    fields={
        "status": serializers.ChoiceField(
            choices=["active", "inactive"],
            help_text="Required. New job status: `active` or `inactive`.",
        ),
    },
)


employee_schema = extend_schema_view(
    list=extend_schema(
        summary="List employees",
        description=(
            "Every employee, or just those employed by one brand when mounted "
            "under a brand. An empty result is an empty list, not a 404."
        ),
        parameters=[BRAND_PK],
        responses={200: EmployeeListResponse},
    ),
    retrieve=extend_schema(
        summary="Retrieve an employee",
        description=(
            "Scoped to a brand they hold a job at when mounted under one: "
            "asking brand 2 for an employee who only works at brand 1 is a 404."
        ),
        parameters=[ID, BRAND_PK],
        responses={
            200: EmployeeResponse,
            404: not_found("No such employee, or none employed by this brand."),
        },
    ),
    create=by_mount(
        "brand_pk",
        present=extend_schema(
            summary="Employ an existing person at a brand",
            description=(
                "Creates **only** the Job linking an existing person to this "
                "brand. It does not create the Employee - `employee_id` must "
                "name someone already recorded via `POST /api/v1/employees`, "
                "and an unknown id is a 404.\n\n"
                "One person may hold more than one job at the same brand (Cook "
                "*and* Cashier), so employing someone already employed here is "
                "a normal 201 producing a second Job, not a conflict. The same "
                "person may equally hold jobs at several brands."
            ),
            parameters=[BRAND_PK],
            request=EmployRequest,
            responses={
                201: OpenApiResponse(
                    response=EmploymentResponse,
                    description="The new Job, with the person it employs.",
                ),
                400: bad_request("`employee_id` or `roles` is missing or malformed."),
                404: not_found(
                    "No such brand, or no such employee."
                ),
            },
            examples=[
                OpenApiExample(
                    "Employ as a barista",
                    value={"employee_id": 7, "roles": "Barista"},
                    request_only=True,
                ),
                OpenApiExample(
                    "Explicit status",
                    value={"employee_id": 7, "role": "Cashier", "status": "active"},
                    request_only=True,
                ),
                OpenApiExample(
                    "No employee_id",
                    value={"error": "employee_id is required"},
                    response_only=True,
                    status_codes=["400"],
                ),
                OpenApiExample(
                    "Unknown employee",
                    value={"detail": "Employee 999 not found"},
                    response_only=True,
                    status_codes=["404"],
                ),
            ],
        ),
        absent=extend_schema(
            summary="Create a person",
            description=(
                "Records that a person exists, from `name` alone. This is the "
                "only place an Employee row is created, and it creates nothing "
                "else - the new person works nowhere until they are employed "
                "via `POST /api/v1/brands/{brand_pk}/employees`."
            ),
            request=CreatePersonRequest,
            responses={
                201: OpenApiResponse(
                    response=EmployeeResponse,
                    description="The new person. No Job is created.",
                ),
                400: bad_request("`name` is missing or blank."),
            },
            examples=[
                OpenApiExample(
                    "Create a person",
                    value={"name": "Amina Hassan"},
                    request_only=True,
                ),
                OpenApiExample(
                    "No name",
                    value={"error": "name is required"},
                    response_only=True,
                    status_codes=["400"],
                ),
            ],
        ),
    ),
    update=extend_schema(
        summary="Change an employee's job status at a brand",
        description=(
            "Edits the Job, not the employee's name, and edits exactly one "
            "field of it: `status`. Sending nothing is a 400.\n\n"
            "A position **cannot** be re-assigned here. A body carrying "
            "`roles`, `role` or `position` is rejected with a 400 rather than "
            "accepted-and-ignored, so a caller who meant to move someone to "
            "another position is told so instead of receiving a 200 that "
            "changed nothing they asked for. To change a position, end this "
            "job and employ the person again via "
            "`POST /api/v1/brands/{brand_pk}/employees`.\n\n"
            "Requires both ids in the URL: "
            "`PUT /api/v1/brands/{brand_pk}/employees/{id}`. A `brand_id` or "
            "`employee_id` in the body is accepted but ignored - the URL is "
            "authoritative."
        ),
        parameters=[ID, BRAND_PK],
        request=UpdateEmploymentRequest,
        responses={
            200: OpenApiResponse(
                response=EmploymentResponse, description="The updated Job and employee."
            ),
            400: bad_request(
                "`status` was not sent, or a `roles`/`role`/`position` key was "
                "sent, or no brand is in the URL."
            ),
            404: not_found("This employee holds no job at this brand."),
        },
        examples=[
            OpenApiExample(
                "Deactivate", value={"status": "inactive"}, request_only=True
            ),
            OpenApiExample(
                "Reinstate", value={"status": "active"}, request_only=True
            ),
            OpenApiExample(
                "Empty body",
                value={"error": "Nothing to update; send 'status'"},
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Tried to re-assign the position",
                value={
                    "error": (
                        "A job's position cannot be changed here; this endpoint "
                        "updates 'status' only"
                    )
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
)
