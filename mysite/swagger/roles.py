"""Schema for ``RoleViewSet``.

Contract read off ``components/role.py``. ``name`` is the only field a role
carries; ``schedule_id`` comes from the URL and a body key of that name is not
read at all.

The only mount is ``brands/{brand_pk}/schedules/{schedule_pk}/roles``, so a
role is only ever looked up within the schedule that owns it, and that schedule
only within its brand: ``RoleComponent.get`` calls ``role_for_schedule``, which
means asking the wrong schedule for a real role is a 404 rather than a hit, and
``create`` resolves the schedule through
``ScheduleComponent.require(schedule_pk, brand_pk=...)``, so a role cannot be
written into another brand's schedule. That is worth documenting because it is
the opposite of what a flat ``/roles/{id}`` would do.
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

from swagger.common import BRAND_PK, ID, SCHEDULE_PK, bad_request, not_found, shape

RoleResponse, RoleListResponse = shape(
    "Role",
    {
        "id": serializers.IntegerField(read_only=True),
        "name": serializers.CharField(),
        "schedule_id": serializers.IntegerField(),
    },
)

RoleRequest = inline_serializer(
    name="RoleRequest",
    fields={
        # Matched against Position.name when staffing.
        "name": serializers.CharField(max_length=100),
    },
)


role_schema = extend_schema_view(
    list=extend_schema(
        summary="List the roles in a schedule",
        parameters=[BRAND_PK, SCHEDULE_PK],
        responses={200: RoleListResponse},
    ),
    retrieve=extend_schema(
        summary="Retrieve a role",
        description=(
            "Scoped to its schedule, and that schedule to its brand: asking "
            "the wrong schedule - or the right schedule under the wrong brand - "
            "for a real role is a 404."
        ),
        parameters=[ID, BRAND_PK, SCHEDULE_PK],
        responses={
            200: RoleResponse,
            404: not_found("No role with this id in this schedule."),
        },
    ),
    create=extend_schema(
        summary="Add a role to a schedule",
        description=(
            "`POST /api/v1/brands/{brand_pk}/schedules/{schedule_pk}/roles`. "
            "`schedule_id` is taken from the URL; a body key of that name is "
            "ignored. The schedule is resolved within the brand, so a schedule "
            "belonging to another brand is a 404. The role's `name` is later "
            "matched against a position name when a shift under it is staffed."
        ),
        parameters=[BRAND_PK, SCHEDULE_PK],
        request=RoleRequest,
        responses={
            201: OpenApiResponse(response=RoleResponse, description="Role created."),
            400: bad_request("`name` is missing or blank."),
            404: not_found(
                "The brand named in the URL does not exist, or that brand has "
                "no schedule with this id."
            ),
        },
        examples=[
            OpenApiExample("Add a role", value={"name": "Barista"}, request_only=True),
            OpenApiExample(
                "Missing name",
                value={"error": "name is required"},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
)
