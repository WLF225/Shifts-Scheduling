"""Marshmallow dump schemas for the domain models."""
from marshmallow import fields, pre_dump
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from database.engine import session
from database.models import (
    Employee,
    Role,
    Brand,
    Shift,
    Job,
    JobStatus,
    Position,
    Schedule,
)


class EmployeeSchema(SQLAlchemyAutoSchema):
    """Serializes Employee rows for responses."""

    class Meta:
        """Binds the schema to Employee."""

        model = Employee
        sqla_session = session
        load_instance = True
        include_fk = True


class BrandSchema(SQLAlchemyAutoSchema):
    """Serializes Brand rows for responses."""

    class Meta:
        """Binds the schema to Brand."""

        model = Brand
        sqla_session = session
        load_instance = True
        include_fk = True


class PositionSchema(SQLAlchemyAutoSchema):
    """Serializes Position rows for responses."""

    class Meta:
        """Binds the schema to Position."""

        model = Position
        sqla_session = session
        load_instance = True
        include_fk = True


class JobSchema(SQLAlchemyAutoSchema):
    """Serializes Job rows for responses."""

    status = fields.Enum(JobStatus, by_value=True)

    class Meta:
        """Binds the schema to Job."""

        model = Job
        sqla_session = session
        load_instance = True
        include_fk = True


class ScheduleSchema(SQLAlchemyAutoSchema):
    """Serializes Schedule rows for responses."""

    class Meta:
        """Binds the schema to Schedule."""

        model = Schedule
        sqla_session = session
        load_instance = True
        include_fk = True


class RoleSchema(SQLAlchemyAutoSchema):
    """Serializes Role rows for responses."""

    class Meta:
        """Binds the schema to Role."""

        model = Role
        sqla_session = session
        load_instance = True
        include_fk = True


class ShiftSchema(SQLAlchemyAutoSchema):
    """Serializes Shift rows for responses."""

    class Meta:
        """Binds the schema to Shift."""

        model = Shift
        sqla_session = session
        load_instance = True
        include_fk = True
