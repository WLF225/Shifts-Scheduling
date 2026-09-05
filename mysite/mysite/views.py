"""Views for the scheduling API.

Every viewset here is thin on purpose: it reads the URL, hands the raw request
body to a component, and serialises what comes back. No view builds a query, no
view coerces input, and no view decides what is allowed - all of that lives in
``components/``, which raises framework-free exceptions that
``mysite.exceptions.repository_exception_handler`` turns into status codes. So
there is no try/except in this module and no repository import either.

Serialisation is marshmallow for the models that have a schema in
``mysite/schemas.py``, and the hand-rolled dicts in ``components.payloads`` for
Job and Shift, whose answers flatten a walk across several tables rather than
one row's columns.

The OpenAPI declarations live in ``swagger/``, one module per resource, and
arrive here as a single ready-made decorator per class. ``@extend_schema`` has
to be applied to the real view callable, so the decorator cannot live anywhere
else - but the payload shapes, examples and typed path parameters can, and do.
They are documentation only: spectacular reads them, the request path does not.
"""
from __future__ import annotations

from rest_framework import status, viewsets
from rest_framework.response import Response

from components.brand import BrandComponent
from components.employee import EmployeeComponent
from components.employee_time import EmployeeTimeComponent
from components.payloads import job_payload, shift_payload
from components.role import RoleComponent
from components.schedule import ScheduleComponent
from components.shift import ShiftComponent
from mysite.schemas import (
    BrandSchema,
    EmployeeSchema,
    RoleSchema,
    ScheduleSchema,
)
from swagger.brands import brand_schema
from swagger.employee_times import employee_time_schema
from swagger.employees import employee_schema
from swagger.roles import role_schema
from swagger.schedules import schedule_schema
from swagger.shifts import shift_schema


@employee_schema
class EmployeeViewSet(viewsets.ViewSet):
    def retrieve(self, request, pk:int | None = None, brand_pk:int | None = None) -> Response:
        """One employee, optionally scoped to a brand they hold a job at."""
        row = EmployeeComponent().get(pk, brand_pk=brand_pk)
        return Response(
            EmployeeSchema(many=False).dump(row), status=status.HTTP_200_OK
        )

    def list(self, request, brand_pk:int | None = None):
        """Every employee, or just those employed by one brand."""
        rows = EmployeeComponent().list(brand_pk=brand_pk)
        return Response(
            EmployeeSchema(many=True).dump(rows), status=status.HTTP_200_OK
        )

    def create(self, request, brand_pk:int | None = None) -> Response:
        """Create a person, or employ an existing one at the brand in the URL.

        The two mounts of this method are two different writes.
        ``POST /employees`` records a person and answers the bare employee;
        ``POST /brands/<id>/employees`` creates only the Job and answers the
        pair, so the caller can see which person it attached.
        """
        if brand_pk is None:
            employee = EmployeeComponent().create_person(request.data)
            return Response(
                EmployeeSchema(many=False).dump(employee),
                status=status.HTTP_201_CREATED,
            )

        employee, job = EmployeeComponent().employ(request.data, brand_pk=brand_pk)
        return Response(
            {
                "employee": EmployeeSchema(many=False).dump(employee),
                "job": job_payload(job),
            },
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, pk:int | None = None, brand_pk:int | None = None) -> Response:
        """Re-assign an employee's job at a brand."""
        job = EmployeeComponent().update_employment(
            request.data, pk=pk, brand_pk=brand_pk
        )
        return Response(
            {
                "employee": EmployeeSchema(many=False).dump(job.employee),
                "job": job_payload(job),
            },
            status=status.HTTP_200_OK,
        )


@employee_time_schema
class EmployeeTimeViewSet(viewsets.ViewSet):
    """``/employees/<id>/times`` - when an employee is booked, and when not."""

    def list(self, request, employee_pk:int | None = None) -> Response:
        payload = EmployeeTimeComponent().times(
            employee_pk=employee_pk, mode=request.query_params.get("mode")
        )
        return Response(payload, status=status.HTTP_200_OK)


@brand_schema
class BrandViewSet(viewsets.ViewSet):
    def retrieve(self, request, pk:int) -> Response:
        brand = BrandComponent().get(pk)
        return Response(BrandSchema(many = False).dump(brand), status=status.HTTP_200_OK)

    def list(self, request):
        """Every brand. An empty result is an empty list, not a 404."""
        brands = BrandComponent().list()
        return Response(BrandSchema(many = True).dump(brands), status=status.HTTP_200_OK)

    def create(self, request) -> Response:
        """Create a brand. Both ``name`` and ``location`` are required."""
        brand = BrandComponent().create(request.data)
        return Response(
            BrandSchema(many=False).dump(brand), status=status.HTTP_201_CREATED
        )


@schedule_schema
class ScheduleViewSet(viewsets.ViewSet):
    def retrieve(self, request, pk:int | None = None, brand_pk:int | None = None) -> Response:
        schedule = ScheduleComponent().get(pk=pk, brand_pk=brand_pk)
        return Response(
            ScheduleSchema(many=False).dump(schedule), status=status.HTTP_200_OK
        )

    def list(self, request, brand_pk:int | None = None) -> Response:
        rows = ScheduleComponent().list(brand_pk=brand_pk)
        return Response(ScheduleSchema(many=True).dump(rows), status=status.HTTP_200_OK)

    def create(self, request, brand_pk:int | None = None) -> Response:
        schedule = ScheduleComponent().create(request.data, brand_pk=brand_pk)
        return Response(
            ScheduleSchema(many=False).dump(schedule), status=status.HTTP_201_CREATED
        )


@role_schema
class RoleViewSet(viewsets.ViewSet):
    """Roles, always addressed under their schedule, itself under its brand.

    The only mount is ``brands/<id>/schedules/<id>/roles``, so both
    ``brand_pk`` and ``schedule_pk`` are always supplied and a role is only
    ever looked up within the schedule that owns it: asking the wrong schedule
    for a real role is a 404, not a hit.

    ``brand_pk`` is captured by the URL and so is passed to every method by
    DRF; a method omitting it would raise ``TypeError``. ``create`` also uses
    it, to resolve the schedule within the brand.
    """

    def retrieve(
        self,
        request,
        pk:int | None = None,
        schedule_pk:int | None = None,
        brand_pk:int | None = None,
    ) -> Response:
        role = RoleComponent().get(pk=pk, schedule_pk=schedule_pk)
        return Response(RoleSchema(many=False).dump(role), status=status.HTTP_200_OK)

    def list(
        self,
        request,
        schedule_pk:int | None = None,
        brand_pk:int | None = None,
    ) -> Response:
        rows = RoleComponent().list(schedule_pk=schedule_pk)
        return Response(RoleSchema(many=True).dump(rows), status=status.HTTP_200_OK)

    def create(
        self,
        request,
        schedule_pk:int | None = None,
        brand_pk:int | None = None,
    ) -> Response:
        """Add a role to a schedule, within the brand that owns it."""
        role = RoleComponent().create(
            request.data, schedule_pk=schedule_pk, brand_pk=brand_pk
        )
        return Response(RoleSchema(many=False).dump(role), status=status.HTTP_201_CREATED)


@shift_schema
class ShiftViewSet(viewsets.ViewSet):
    """Shifts, reachable under a role or under an employee - nothing else.

    Two mounts:
    ``brands/<brand_pk>/schedules/<schedule_pk>/roles/<role_pk>/shifts[/<id>]``,
    the only writable one, and ``employees/<employee_pk>/shifts[/<id>]``, the
    person's own calendar. There is no schedule-level shift mount: a shift
    belongs to a role, and a schedule alone never addresses one.

    Which parent is present decides what a verb means: ``create`` and
    ``update`` need a role, so the employee mount is read-only - its POST and
    PUT are excluded at the router rather than left to fail in the component.

    The role-side mount carries ``brand_pk`` and ``schedule_pk``, because the
    schedule subtree hangs off ``brands/<id>/``. ``brand_pk`` is accepted
    rather than used: the scoping it exists for is already done by the time a
    shift is reached - the role is resolved within its schedule, and the
    schedule within its brand. The employee-side mount carries neither, which
    is why both stay optional.
    """

    def list(
        self,
        request,
        role_pk:int | None = None,
        schedule_pk:int | None = None,
        employee_pk:int | None = None,
        brand_pk:int | None = None,
    ) -> Response:
        rows = ShiftComponent().list(
            role_pk=role_pk, schedule_pk=schedule_pk, employee_pk=employee_pk
        )
        return Response([shift_payload(row) for row in rows], status=status.HTTP_200_OK)

    def retrieve(
        self,
        request,
        pk:int | None = None,
        role_pk:int | None = None,
        schedule_pk:int | None = None,
        employee_pk:int | None = None,
        brand_pk:int | None = None,
    ) -> Response:
        """One shift, scoped to whichever parents the URL names."""
        shift = ShiftComponent().get(
            pk=pk,
            role_pk=role_pk,
            schedule_pk=schedule_pk,
            employee_pk=employee_pk,
        )
        return Response(shift_payload(shift), status=status.HTTP_200_OK)

    # POST /api/v1/brands/{brand_pk}/schedules/{schedule_pk}/roles/{role_pk}/shifts
    def create(
        self,
        request,
        schedule_pk:int | None = None,
        role_pk:int | None = None,
        brand_pk:int | None = None,
    ) -> Response:
        """Create an unstaffed slot: role, date and span, nobody on it."""
        shift = ShiftComponent().create(
            request.data, schedule_pk=schedule_pk, role_pk=role_pk
        )
        return Response(shift_payload(shift), status=status.HTTP_201_CREATED)

    def update(
        self,
        request,
        pk:int | None = None,
        schedule_pk:int | None = None,
        role_pk:int | None = None,
        employee_pk:int | None = None,
        brand_pk:int | None = None,
    ) -> Response:
        """Retime a shift, staff it, or unstaff it - the one write on a slot.

        ``employee_pk`` is now never populated here: the employee mount excludes
        PUT at the router, so this method is only ever reached under a role. It
        is kept because the component's ``update`` still accepts it, and the
        only URL that could supply it no longer routes to a write.
        """
        shift = ShiftComponent().update(
            request.data,
            pk=pk,
            schedule_pk=schedule_pk,
            role_pk=role_pk,
            employee_pk=employee_pk,
        )
        return Response(shift_payload(shift), status=status.HTTP_200_OK)
