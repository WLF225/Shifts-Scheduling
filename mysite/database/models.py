from sqlalchemy import (
    Column, String, Integer, Date, Time, DateTime, Boolean, ForeignKey,
)
from sqlalchemy.orm import relationship, declarative_base, declared_attr


class Base(declarative_base()):

    __abstract__ = True

    @declared_attr
    def id(cls):
        return Column(Integer, primary_key=True, autoincrement=True)


class Employee(Base):
    __tablename__ = "employees"

    name = Column(String(100), nullable=False)

    jobs = relationship("Job", back_populates="employee")


class Brand(Base):
    __tablename__ = "brands"

    name = Column(String(100), nullable=False)
    location = Column(String(255))

    jobs = relationship("Job", back_populates="brand")
    schedules = relationship("Schedule", back_populates="brand")


class Position(Base):
    __tablename__ = "positions"

    name = Column(String(100), nullable=False)

    jobs = relationship("Job", back_populates="position")


class Job(Base):
    __tablename__ = "jobs"

    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=False)
    status = Column(String(50), nullable=False, default="active")

    brand = relationship("Brand", back_populates="jobs")
    employee = relationship("Employee", back_populates="jobs")
    position = relationship("Position", back_populates="jobs")
    shifts = relationship("Shift", back_populates="job")


class Schedule(Base):
    __tablename__ = "schedules"

    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    starting_date = Column(Date, nullable=False)
    created_by = Column(Integer, ForeignKey("employees.id"))

    brand = relationship("Brand", back_populates="schedules")
    creator = relationship("Employee")
    roles = relationship("Role", back_populates="schedule")


class Role(Base):
    __tablename__ = "roles"

    name = Column(String(100), nullable=False)
    schedule_id = Column(Integer, ForeignKey("schedules.id"), nullable=False)

    schedule = relationship("Schedule", back_populates="roles")
    shifts = relationship("Shift", back_populates="role")


class Shift(Base):
    __tablename__ = "shifts"

    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    starting_time = Column(Time, nullable=False)
    finishing_time = Column(Time, nullable=False)
    date = Column(Date, nullable=False)

    job = relationship("Job", back_populates="shifts")
    role = relationship("Role", back_populates="shifts")


class Manager(Base):
    """A user that can authenticate.

    Only ``password_hash`` is ever stored; the raw password is hashed in
    ``auth.service`` and never persisted or logged.
    """
    __tablename__ = "managers"

    username = Column(String(100), nullable=False, unique=True)
    email = Column(String(255), unique=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    refresh_tokens = relationship(
        "RefreshToken", back_populates="manager", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    """A stored, revocable refresh token.

    Access tokens are stateless JWTs and are never stored. Refresh tokens are
    persisted so that logout can revoke a session immediately and so rotation
    can detect reuse of an already-spent token.
    """
    __tablename__ = "refresh_tokens"

    manager_id = Column(Integer, ForeignKey("managers.id"), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime)

    manager = relationship("Manager", back_populates="refresh_tokens")
