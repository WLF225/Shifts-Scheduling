"""Schema for ``ScheduleViewSet``.

Contract read off ``components/schedule.py``. One detail the field list alone
does not convey:

**A schedule is always addressed under its brand.** The only mount is
``brands/{brand_pk}/schedules``, so ``brand_pk`` is required on every
operation - there is no unnested ``/api/v1/schedules`` path to document. The
rule is enforced twice over: routing offers no other URL, and
``ScheduleComponent`` raises a ``ValidationError`` if ``brand_pk`` is ever
None, so it cannot be lost by a re-registered router.

Nothing here sets an ``operation_id``; see ``swagger.common``.
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

from swagger.common import BRAND_PK, ID, bad_request, not_found, shape

ScheduleResponse, ScheduleListResponse = shape(
    "Schedule",
    {
        "id": serializers.IntegerField(read_only=True),
        "brand_id": serializers.IntegerField(),
        "starting_date": serializers.DateField(),
    },
)

ScheduleRequest = inline_serializer(
    name="ScheduleRequest",
    fields={
        "starting_date": serializers.CharField(
            help_text=(
                "Required. Accepts D/M/YYYY or YYYY-MM-DD. Alias: `date`."
            ),
        ),
    },
)


schedule_schema = extend_schema_view(
    list=extend_schema(
        summary="List a brand's schedules",
        description=(
            "Every schedule belonging to the brand in the URL. There is no "
            "cross-brand listing: a schedule is only ever addressed under its "
            "brand."
        ),
        parameters=[BRAND_PK],
        responses={200: ScheduleListResponse},
    ),
    retrieve=extend_schema(
        summary="Retrieve a schedule",
        description=(
            "Scoped to the brand in the URL: asking the wrong brand for a real "
            "schedule is a 404, not a hit."
        ),
        parameters=[ID, BRAND_PK],
        responses={
            200: ScheduleResponse,
            404: not_found("No schedule with this id, or not under this parent."),
        },
    ),
    create=extend_schema(
        summary="Open a schedule for a brand",
        description=(
            "`POST /api/v1/brands/{brand_pk}/schedules` - the only way to open "
            "a schedule. `brand_id` is taken from the URL; a body key of that "
            "name is not read."
        ),
        parameters=[BRAND_PK],
        request=ScheduleRequest,
        responses={
            201: OpenApiResponse(
                response=ScheduleResponse, description="Schedule created."
            ),
            400: bad_request("`starting_date` is missing or unparseable."),
            404: not_found("The brand named in the URL does not exist."),
        },
        examples=[
            OpenApiExample(
                "D/M/YYYY date",
                value={"starting_date": "7/9/2026"},
                request_only=True,
            ),
            OpenApiExample(
                "ISO date",
                value={"starting_date": "2026-09-07"},
                request_only=True,
            ),
            OpenApiExample(
                "Unparseable date",
                value={"error": "starting_date is required"},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
)
