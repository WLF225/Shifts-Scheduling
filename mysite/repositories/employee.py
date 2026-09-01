from typing import Sequence

from database.engine import session
from database.models import Employee, Brand, Job
from repositories.base import BaseRepository
from repositories.exceptions import InvalidFilter


class EmployeeRepository(BaseRepository[Employee]):
    model = Employee

    def employees_for_brand(self, brand_pk: int) ->Sequence[Employee]:
        if brand_pk is None:
            raise InvalidFilter()
        return (
            self.session.query(Employee)
            .join(Job, Job.employee_id==Employee.id)
            .filter(Job.brand_id == brand_pk)
            .distinct(Employee.employee_id).all()
        )

    def employee_for_brand(self, brand_pk: int, employee_pk: int) -> Employee | None:
        if brand_pk is None or employee_pk is None:
            raise InvalidFilter()
        return (
            self.session.query(Employee)
            .join(Job, Job.employee_id==Employee.id)
            .filter(Job.brand_id == brand_pk, Employee.employee_id == employee_pk)
            .one_or_none()
        )

