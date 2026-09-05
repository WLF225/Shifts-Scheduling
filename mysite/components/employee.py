"""Business rules for employees and the jobs that employ them.

A person and their employment are two separate writes, because they are two
separate facts. :meth:`EmployeeComponent.create_person` records that someone
exists; :meth:`EmployeeComponent.employ` records that an *existing* person
holds a position at a brand. Employing therefore never mints an Employee row -
it resolves one by id and 404s if there is none - which is what lets one person
hold jobs at several brands, and more than one job at the same brand (Cook and
Cashier is a real case, so no duplicate-employment check is made here).
"""
from __future__ import annotations

from typing import Any, Sequence

from components.base import BaseComponent
from components.brand import BrandComponent
from components.exceptions import NotFound, ValidationError
from components.parsing import body_dict, parse_int, pick, require_text
from database.models import Employee, Job
from repositories.employee import EmployeeRepository
from repositories.job import JobRepository
from repositories.position import PositionRepository


class EmployeeComponent(BaseComponent):

    def get(self, pk, brand_pk=None) -> Employee:

        employees = self._repo(EmployeeRepository)
        row = (employees.get(pk) if brand_pk is None else employees.employee_for_brand(brand_pk, pk))
        if row is None:
            raise NotFound(f"Employee {pk} not found")
        return row

    def list(self, brand_pk=None) -> Sequence[Employee]:

        employees = self._repo(EmployeeRepository)

        return employees.list() if brand_pk is None else employees.employees_for_brand(brand_pk)

    def create_person(self, data: Any) -> Employee:
        """Record that a person exists. ``name`` is the whole payload.

        The only place an Employee row is created. It deliberately takes no
        brand: someone can be on the books before anyone has decided where they
        work, and :meth:`employ` is what attaches them to a brand afterwards.
        """
        body = body_dict(data)
        name = require_text(pick(body, "name"), "name")
        return self._repo(EmployeeRepository).create(name=name)

    def employ(self, data: Any, brand_pk=None) -> tuple[Employee, Job]:
        """Employ an *existing* person at a brand, creating only the Job.

        ``employee_id`` names the person; an unknown one is a
        :class:`~components.exceptions.NotFound`, the same answer the rest of
        this module gives for a row that is not there, rather than a silent
        create. Holding a second job at the same brand is allowed - the pair
        (Cook, Cashier) is a real arrangement - so no duplicate check is made.

        The employee is returned alongside the job even though only the job is
        written, because the caller addressed the person by id and the response
        envelope is what confirms *which* person got employed.
        """
        if brand_pk is None:
            raise ValidationError(
                "An employment must be created under a brand: POST /brands/<id>/employees"
            )

        brand = BrandComponent(self.session).require(brand_pk)

        body = body_dict(data)
        raw_employee_id = pick(body, "employee_id", "employee")
        if raw_employee_id is None:
            raise ValidationError("employee_id is required")
        employee_id = parse_int(raw_employee_id, "employee_id")
        position_name = require_text(pick(body, "roles", "role", "position"), "roles")
        job_status = require_text(pick(body, "status", default="active"), "status", 50)

        employee = self._repo(EmployeeRepository).get(employee_id)
        if employee is None:
            raise NotFound(f"Employee {employee_id} not found")

        position = self._repo(PositionRepository).get_or_create(position_name)
        job = self._repo(JobRepository).create(
            brand_id=brand.id,
            employee_id=employee.id,
            position_id=position.id,
            status=job_status,
        )
        return employee, job

    def update_employment(self, data: Any, pk=None, brand_pk=None) -> Job:

        if brand_pk is None or pk is None:
            raise ValidationError("An employment must be updated under a brand: PUT /brands/<id>/employees/<id>")

        jobs = self._repo(JobRepository)
        job = jobs.for_brand_and_employee(brand_pk, pk)
        if job is None:
            raise NotFound(f"Employee {pk} has no job at brand {brand_pk}")

        body = body_dict(data)
        changes = {}
        raw_position = pick(body, "roles", "role", "position")
        if raw_position is not None:
            position_name = require_text(raw_position, "roles")
            changes["position_id"] = (
                self._repo(PositionRepository).get_or_create(position_name).id
            )
        raw_status = pick(body, "status")
        if raw_status is not None:
            changes["status"] = require_text(raw_status, "status", 50)

        if not changes:
            raise ValidationError("Nothing to update; send 'roles' and/or 'status'")

        return jobs.update(job, **changes)
