"""DRF viewsets; every rule lives in components."""
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
    """Employees, mounted globally and under a brand."""
    def retrieve(self, request, pk:int | None = None, brand_pk:int | None = None) -> Response:
        """One employee, optionally scoped to a brand."""
        row = EmployeeComponent().get(pk, brand_pk=brand_pk)
        return Response(
            EmployeeSchema(many=False).dump(row), status=status.HTTP_200_OK
        )

    def list(self, request, brand_pk:int | None = None):
        """Every employee, or only one brand's."""
        rows = EmployeeComponent().list(brand_pk=brand_pk)
        return Response(EmployeeSchema(many=True).dump(rows), status=status.HTTP_200_OK)

    def create(self, request, brand_pk:int | None = None) -> Response:
        """Record a person, or employ one somewhere."""
        if brand_pk is None:
            employee = EmployeeComponent().create_person(request.data)
            return Response(EmployeeSchema(many=False).dump(employee),status=status.HTTP_201_CREATED)

        employee, job = EmployeeComponent().employ(request.data, brand_pk=brand_pk)
        return Response({"employee": EmployeeSchema(many=False).dump(employee),"job": job_payload(job),},status=status.HTTP_201_CREATED)

    def update(self, request, pk:int | None = None, brand_pk:int | None = None) -> Response:
        """Change an employee's job status."""
        job = EmployeeComponent().update_employment(request.data, pk=pk, brand_pk=brand_pk)
        return Response({"employee": EmployeeSchema(many=False).dump(job.employee),"job": job_payload(job),},
                        status=status.HTTP_200_OK,)


@employee_time_schema
class EmployeeTimeViewSet(viewsets.ViewSet):
    """When an employee is booked, and when not."""

    def list(self, request, employee_pk:int | None = None) -> Response:
        """One employee's busy blocks and free gaps."""
        payload = EmployeeTimeComponent().times(
            employee_pk=employee_pk, mode=request.query_params.get("mode")
        )
        return Response(payload, status=status.HTTP_200_OK)


@brand_schema
class BrandViewSet(viewsets.ViewSet):
    """Brands: the root of the scheduling tree."""
    def retrieve(self, request, pk:int) -> Response:
        """One brand by id."""
        brand = BrandComponent().get(pk)
        return Response(BrandSchema(many = False).dump(brand), status=status.HTTP_200_OK)

    def list(self, request):
        """Every brand; no results is an empty list."""
        brands = BrandComponent().list()
        return Response(BrandSchema(many = True).dump(brands), status=status.HTTP_200_OK)

    def create(self, request) -> Response:
        """Create a brand; name and location required."""
        brand = BrandComponent().create(request.data)
        return Response(BrandSchema(many=False).dump(brand), status=status.HTTP_201_CREATED)


@schedule_schema
class ScheduleViewSet(viewsets.ViewSet):
    """Weekly schedules, always under their brand."""
    def retrieve(self, request, pk:int | None = None, brand_pk:int | None = None) -> Response:
        """One schedule, scoped to its brand."""
        schedule = ScheduleComponent().get(pk=pk, brand_pk=brand_pk)
        return Response(
            ScheduleSchema(many=False).dump(schedule), status=status.HTTP_200_OK
        )

    def list(self, request, brand_pk:int | None = None) -> Response:
        """One brand's schedules."""
        rows = ScheduleComponent().list(brand_pk=brand_pk)
        return Response(ScheduleSchema(many=True).dump(rows), status=status.HTTP_200_OK)

    def create(self, request, brand_pk:int | None = None) -> Response:
        """Open a schedule week for a brand."""
        schedule = ScheduleComponent().create(request.data, brand_pk=brand_pk)
        return Response(ScheduleSchema(many=False).dump(schedule), status=status.HTTP_201_CREATED)


@role_schema
class RoleViewSet(viewsets.ViewSet):
    """Roles, always addressed under their schedule."""

    def retrieve(self,request,pk:int | None = None,schedule_pk:int | None = None,brand_pk:int | None = None,) -> Response:
        """One role, scoped to its schedule."""
        role = RoleComponent().get(pk=pk, schedule_pk=schedule_pk)
        return Response(RoleSchema(many=False).dump(role), status=status.HTTP_200_OK)

    def list(
        self,
        request,
        schedule_pk:int | None = None,
        brand_pk:int | None = None,
    ) -> Response:
        """One schedule's roles."""
        rows = RoleComponent().list(schedule_pk=schedule_pk)
        return Response(RoleSchema(many=True).dump(rows), status=status.HTTP_200_OK)

    def create(
        self,
        request,
        schedule_pk:int | None = None,
        brand_pk:int | None = None,
    ) -> Response:
        """Add a role to a schedule."""
        role = RoleComponent().create(
            request.data, schedule_pk=schedule_pk, brand_pk=brand_pk
        )
        return Response(RoleSchema(many=False).dump(role), status=status.HTTP_201_CREATED)


@shift_schema
class ShiftViewSet(viewsets.ViewSet):
    """Shifts under a role; read-only under an employee."""

    def list(self,request,role_pk:int | None = None,schedule_pk:int | None = None,
             employee_pk:int | None = None, brand_pk:int | None = None,) -> Response:
        """Shifts under one role, or one employee's."""
        rows = ShiftComponent().list(role_pk=role_pk, employee_pk=employee_pk)
        return Response([shift_payload(row) for row in rows], status=status.HTTP_200_OK)

    def retrieve(self,request,pk:int | None = None,
        role_pk:int | None = None,schedule_pk:int | None = None,employee_pk:int | None = None,brand_pk:int | None = None,) -> Response:
        """One shift, scoped to the URL's parents."""
        shift = ShiftComponent().get(pk=pk,role_pk=role_pk,schedule_pk=schedule_pk,employee_pk=employee_pk)
        return Response(shift_payload(shift), status=status.HTTP_200_OK)

    def create(
        self,
        request,
        schedule_pk:int | None = None,
        role_pk:int | None = None,
        brand_pk:int | None = None,
    ) -> Response:
        """Create an unstaffed slot: date and span only."""
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
        brand_pk:int | None = None,
    ) -> Response:
        """Staffs, retimes, or unstaffs one shift."""
        shift = ShiftComponent().update(
            request.data,
            pk=pk,
            schedule_pk=schedule_pk,
            role_pk=role_pk,
        )
        return Response(shift_payload(shift), status=status.HTTP_200_OK)
