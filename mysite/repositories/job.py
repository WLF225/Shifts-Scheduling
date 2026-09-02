from typing import Sequence

from database.models import Job, Position
from repositories.base import BaseRepository
from repositories.exceptions import InvalidFilter


class JobRepository(BaseRepository[Job]):
    model = Job

    def for_brand_and_employee(self, brand_pk: int, employee_pk: int) -> Job | None:
        """The employment link between a brand and an employee, or ``None``."""
        if brand_pk is None or employee_pk is None:
            raise InvalidFilter("brand_pk and employee_pk are both required")
        return (
            self.session.query(Job)
            .filter(Job.brand_id == brand_pk, Job.employee_id == employee_pk)
            .first()
        )

    def by_position_name(
        self, brand_pk: int, position_name: str, status: str | None = "active"
    ) -> Sequence[Job]:
        """Jobs in a brand whose position is named ``position_name``.

        Used to resolve "which employee works this role" when a shift is posted
        without an explicit job id.
        """
        if brand_pk is None or not position_name:
            raise InvalidFilter("brand_pk and position_name are both required")
        query = (
            self.session.query(Job)
            .join(Position, Position.id == Job.position_id)
            .filter(Job.brand_id == brand_pk, Position.name == position_name)
        )
        if status is not None:
            query = query.filter(Job.status == status)
        return query.all()

    def for_employee(self, employee_pk: int) -> Sequence[Job]:
        if employee_pk is None:
            raise InvalidFilter("employee_pk is required")
        return self.session.query(Job).filter(Job.employee_id == employee_pk).all()
