"""Schema for ``EmployeeTimeViewSet`` - ``/employees/{id}/times``.

Contract read off ``components/employee_time.py``. This is the one computed
answer in the API and the only endpoint with a query parameter, so it was also
the worst-documented: a plain ``ViewSet`` with no serializer emitted an empty
response body and no mention of ``mode`` at all.

Two behaviours a reader cannot guess from the field list:

* ``mode`` is comma-separated and *omitting it means both*, per
  ``parse_modes``. Repeats are collapsed; an unknown value is a 400.
* ``free`` only reports days the employee already works. A day with no shift is
  free by definition, and listing every such day would be an unbounded answer.

The 200 is a single envelope, not a list, even though DRF routes this as the
``list`` action. Declaring the response without ``many=True`` is not enough on
its own - ``AutoSchema._is_list_view`` keys off ``view.action`` before it looks
at the response, and wrapped both the schema and the example in an array the
endpoint never returns. ``swagger.common.PathParameterSchema`` corrects that.
"""
from __future__ import annotations

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers

from swagger.common import EMPLOYEE_PK, bad_request, not_found, shape

_, BusyBlockList = shape(
    "BusyBlock",
    {
        "shift_id": serializers.IntegerField(),
        "date": serializers.DateField(allow_null=True),
        "starting_time": serializers.TimeField(),
        "finishing_time": serializers.TimeField(),
        "role": serializers.CharField(allow_null=True),
        "brand": serializers.CharField(allow_null=True),
    },
    required=False,
)

_, FreeBlockList = shape(
    "FreeBlock",
    {
        "date": serializers.DateField(allow_null=True),
        "starting_time": serializers.TimeField(),
        "finishing_time": serializers.TimeField(),
    },
    required=False,
)

# Each key follows its mode.
EmployeeTimesResponse = inline_serializer(
    name="EmployeeTimes",
    fields={
        "employee_id": serializers.IntegerField(),
        "busy": BusyBlockList,
        "free": FreeBlockList,
    },
)

MODE = OpenApiParameter(
    name="mode",
    type=str,
    location=OpenApiParameter.QUERY,
    required=False,
    enum=["free", "busy", "free,busy"],
    description=(
        "Which blocks to compute, comma-separated. Omit for both. Unknown "
        "values are a 400."
    ),
)


employee_time_schema = extend_schema_view(
    list=extend_schema(
        summary="An employee's booked and free time",
        description=(
            "`busy` is the employee's shifts across every job they hold. "
            "`free` is the complement of those blocks within the 00:00-23:59 "
            "window, reported only for days the employee already works."
        ),
        parameters=[EMPLOYEE_PK, MODE],
        # Kept an object by PathParameterSchema._is_list_view.
        responses={
            200: EmployeeTimesResponse,
            400: bad_request("`mode` names something other than free or busy."),
            404: not_found("No employee with this id."),
        },
        examples=[
            OpenApiExample(
                "Both modes",
                value={
                    "employee_id": 1,
                    "busy": [
                        {
                            "shift_id": 1,
                            "date": "2026-09-07",
                            "starting_time": "08:00:00",
                            "finishing_time": "16:00:00",
                            "role": "Manager",
                            "brand": "Bean & Board",
                        }
                    ],
                    "free": [
                        {
                            "date": "2026-09-07",
                            "starting_time": "00:00:00",
                            "finishing_time": "08:00:00",
                        },
                        {
                            "date": "2026-09-07",
                            "starting_time": "16:00:00",
                            "finishing_time": "23:59:00",
                        },
                    ],
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Unknown mode",
                value={"error": "mode 'nope' is not valid; expected one of busy, free"},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
)
