"""Business rules for employees and their jobs."""
from __future__ import annotations

from typing import Any, Sequence

from components.base import BaseComponent
from components.brand import BrandComponent
from components.exceptions import NotFound, ValidationError
from components.parsing import body_dict, has_key, parse_int, pick, require_text
from database.models import Employee, Job, JobStatus
from repositories.employee import EmployeeRepository
from repositories.job import JobRepository
from repositories.position import PositionRepository


def _parse_status(value: Any) -> JobStatus:
    """Coerce a status, rejecting anything unknown."""
    text = require_text(value, "status", 50).lower()
    try:
        return JobStatus(text)
    except ValueError:
        allowed = ", ".join(member.value for member in JobStatus)
        raise ValidationError(f"status {text!r} is not valid; expected one of {allowed}") from None


class EmployeeComponent(BaseComponent):
    """Reads people; writes the jobs that employ them."""

    def get(self, pk, brand_pk=None) -> Employee:
        """One employee, optionally scoped to a brand."""
        employees = self._repo(EmployeeRepository)
        row = employees.get(pk) if brand_pk is None else employees.employee_for_brand(brand_pk, pk)
        if row is None:
            raise NotFound(f"Employee {pk} not found")
        return row

    def list(self, brand_pk=None) -> Sequence[Employee]:
        """Every employee, or only one brand's."""
        employees = self._repo(EmployeeRepository)

        return employees.list() if brand_pk is None else employees.employees_for_brand(brand_pk)

    def create_person(self, data: Any) -> Employee:
        """Record that a person exists; name only."""
        body = body_dict(data)
        name = require_text(pick(body, "name"), "name")
        return self._repo(EmployeeRepository).create(name=name)

    def employ(self, data: Any, brand_pk=None) -> tuple[Employee, Job]:
        """Employ an existing person at a brand."""
        if brand_pk is None:
            raise ValidationError("An employment must be created under a brand: POST /brands/<id>/employees")

        brand = BrandComponent(self.session).require(brand_pk)

        body = body_dict(data)
        raw_employee_id = pick(body, "employee_id", "employee")
        if raw_employee_id is None:
            raise ValidationError("employee_id is required")
        employee_id = parse_int(raw_employee_id, "employee_id")
        position_name = require_text(pick(body, "roles", "role", "position"), "roles")
        job_status = _parse_status(pick(body, "status", default=JobStatus.ACTIVE.value))

        employee = self._repo(EmployeeRepository).get(employee_id)
        if employee is None:
            raise NotFound(f"Employee {employee_id} not found")

        position = self._repo(PositionRepository).get_or_create(position_name)
        job = self._repo(JobRepository).create(brand_id=brand.id,employee_id=employee.id,position_id=position.id,status=job_status,)
        return employee, job

    def update_employment(self, data: Any, pk, brand_pk) -> Job:
        """Change an employee's job status."""
        jobs = self._repo(JobRepository)
        job = jobs.for_brand_and_employee(brand_pk, pk)
        if job is None:
            raise NotFound(f"Employee {pk} has no job at brand {brand_pk}")

        body = body_dict(data)
        if has_key(body, "roles", "role", "position"):
            raise ValidationError("A job's position cannot be changed here; this endpoint updates 'status' only")
        raw_status = pick(body, "status")
        if raw_status is None:
            raise ValidationError("Nothing to update; send 'status'")

        return jobs.update(job, status=_parse_status(raw_status))
