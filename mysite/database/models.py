"""SQLAlchemy models for the scheduling domain."""
from enum import StrEnum

from sqlalchemy import (
    Column, String, Integer, Date, Time, ForeignKey, Enum as SAEnum,
)
from sqlalchemy.orm import relationship, declarative_base, declared_attr


class JobStatus(StrEnum):
    """Whether a job may still be scheduled."""

    ACTIVE = "active"
    INACTIVE = "inactive"


class Base(declarative_base()):
    """Declarative base giving every table an id."""

    __abstract__ = True

    @declared_attr
    def id(cls):
        """Autoincrementing integer primary key column."""
        return Column(Integer, primary_key=True, autoincrement=True)


class Employee(Base):
    """A person who can hold jobs."""

    __tablename__ = "employees"

    name = Column(String(100), nullable=False)

    jobs = relationship("Job", back_populates="employee")


class Brand(Base):
    """A company owning jobs and schedules."""

    __tablename__ = "brands"

    name = Column(String(100), nullable=False)
    location = Column(String(255), nullable=False)

    jobs = relationship("Job", back_populates="brand")
    schedules = relationship("Schedule", back_populates="brand")


class Position(Base):
    """A job title an employee can hold."""

    __tablename__ = "positions"

    name = Column(String(100), nullable=False)

    jobs = relationship("Job", back_populates="position")


class Job(Base):
    """Employment of one employee at one brand."""

    __tablename__ = "jobs"

    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=False)
    status = Column(SAEnum(JobStatus, values_callable=lambda e: [m.value for m in e]),nullable=False,
    default=JobStatus.ACTIVE,server_default=JobStatus.ACTIVE.value,)

    brand = relationship("Brand", back_populates="jobs")
    employee = relationship("Employee", back_populates="jobs")
    position = relationship("Position", back_populates="jobs")
    shifts = relationship("Shift", back_populates="job")


class Schedule(Base):
    """One brand's week of roles and shifts."""

    __tablename__ = "schedules"

    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    starting_date = Column(Date, nullable=False)

    brand = relationship("Brand", back_populates="schedules")
    roles = relationship("Role", back_populates="schedule")


class Role(Base):
    """A staffed position within one schedule."""

    __tablename__ = "roles"

    name = Column(String(100), nullable=False)
    schedule_id = Column(Integer, ForeignKey("schedules.id"), nullable=False)

    schedule = relationship("Schedule", back_populates="roles")
    shifts = relationship("Shift", back_populates="role")


class Shift(Base):
    """One worked interval in a role's slot."""

    __tablename__ = "shifts"

    # Null until an employee is assigned.
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    starting_time = Column(Time, nullable=False)
    finishing_time = Column(Time, nullable=False)
    date = Column(Date, nullable=False)

    job = relationship("Job", back_populates="shifts")
    role = relationship("Role", back_populates="shifts")
