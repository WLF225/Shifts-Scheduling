from sqlalchemy import Column, String, Integer, Date, Time, ForeignKey
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
