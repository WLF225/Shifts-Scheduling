from rest_framework import viewsets, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from mysite import exceptions
from database.models import Employee
from mysite.schemas import (
    EmployeeSchema,
    RoleSchema,
    BrandSchema,
    ShiftSchema,
    JobSchema,
    PositionSchema,
    ScheduleSchema,
    ManagerSchema,
)
from repositories.brand import BrandRepository
from repositories.employee import EmployeeRepository
from repositories.job import JobRepository


class EmployeeViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def retrieve(self, request, pk:int | None = None, brand_pk:int | None = None) -> Response:
        employee = EmployeeRepository()
        if pk is not None and brand_pk is None:
            row = EmployeeSchema(many=False).dump(employee.get(pk))
            if row is None:
                raise exceptions.NotFound("Employee not found", status.HTTP_404_NOT_FOUND)
            return Response(row, status=status.HTTP_200_OK)
        else:
            row = EmployeeSchema(many = False).dump(employee.employee_for_brand(brand_pk, pk))
            if row is None:
                raise exceptions.NotFound("Employee not found", status.HTTP_404_NOT_FOUND)
            return Response(row, status=status.HTTP_200_OK)

    def list(self, request, brand_pk:int | None = None):
        employee = EmployeeRepository()

        if brand_pk is None:
            row = EmployeeSchema(many = True).dump(employee.list())
            if row is None:
                raise exceptions.NotFound("Employee not found", status.HTTP_404_NOT_FOUND)
            return Response(row, status=status.HTTP_200_OK)

        else:
            row = EmployeeSchema(many = True).dump(employee.employees_for_brand(brand_pk))
            if row is None:
                raise exceptions.NotFound("Employee not found", status.HTTP_404_NOT_FOUND)
            return Response(row, status=status.HTTP_200_OK)



class BrandViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def list(self, request):
        brand = BrandRepository()
        return Response(BrandSchema(many = True).dump(brand.list()), status=status.HTTP_200_OK)
