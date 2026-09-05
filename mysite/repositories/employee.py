"""Repository for employee rows."""
from typing import Sequence

from database.engine import session
from database.models import Employee, Brand, Job
from repositories.base import BaseRepository
from repositories.exceptions import InvalidFilter


class EmployeeRepository(BaseRepository[Employee]):
    """Queries over employees, scoped through their jobs."""

    model = Employee

    def employees_for_brand(self, brand_pk: int) ->Sequence[Employee]:
        """Every employee holding a job at this brand."""
        if brand_pk is None:
            raise InvalidFilter()
        return (
            self.session.query(Employee)
            .join(Job, Job.employee_id==Employee.id)
            .filter(Job.brand_id == brand_pk)
            .distinct(Employee.id).all()
        )

    def employee_for_brand(self, brand_pk: int, employee_pk: int) -> Employee | None:
        """One employee, only if employed by this brand."""
        if brand_pk is None or employee_pk is None:
            raise InvalidFilter()
        return (
            self.session.query(Employee)
            .join(Job, Job.employee_id==Employee.id)
            .filter(Job.brand_id == brand_pk, Employee.id == employee_pk)
            .one_or_none()
        )

