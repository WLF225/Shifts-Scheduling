from marshmallow import Schema, fields, pre_dump, validate
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
    Manager,
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


class ManagerSchema(SQLAlchemyAutoSchema):
    """Serialises a manager. ``password_hash`` is never exposed."""

    class Meta:
        model = Manager
        sqla_session = session
        load_instance = True
        include_fk = True
        exclude = ("password_hash",)


class RegisterSchema(Schema):
    """Validates the register payload. ``password`` is load_only, so it can
    never be echoed back in a response."""

    username = fields.Str(required=True, validate=validate.Length(min=3, max=100))
    email = fields.Email(required=False, allow_none=True)
    password = fields.Str(
        required=True, load_only=True, validate=validate.Length(min=8, max=128)
    )


class LoginSchema(Schema):
    username = fields.Str(required=True)
    password = fields.Str(required=True, load_only=True)


class RefreshSchema(Schema):
    refresh_token = fields.Str(required=True)
