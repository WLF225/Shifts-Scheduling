from marshmallow import fields, pre_dump
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from database.engine import session
from database.models import (
    Employee,
    Role,
    Brand,
    Shift,
    Job,
    Position,
    Schedule,
)


class EmployeeSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Employee
        sqla_session = session
        load_instance = True
        include_fk = True


class BrandSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Brand
        sqla_session = session
        load_instance = True
        include_fk = True


class PositionSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Position
        sqla_session = session
        load_instance = True
        include_fk = True


class JobSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Job
        sqla_session = session
        load_instance = True
        include_fk = True


class ScheduleSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Schedule
        sqla_session = session
        load_instance = True
        include_fk = True


class RoleSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Role
        sqla_session = session
        load_instance = True
        include_fk = True


class ShiftSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Shift
        sqla_session = session
        load_instance = True
        include_fk = True
