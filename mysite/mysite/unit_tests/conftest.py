"""Stubs the engine, then boots Django."""
from __future__ import annotations

import os
import sys
import types
from datetime import date, time
from importlib.machinery import ModuleSpec
from pathlib import Path
from unittest.mock import MagicMock

PYTHON_ROOT = Path(__file__).resolve().parents[2]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))


def _install_engine_stub() -> types.ModuleType:
    """Replaces database.engine before anything imports it."""
    stub = types.ModuleType("database.engine")
    stub.engine = MagicMock(name="engine")
    stub.Session = MagicMock(name="Session")
    stub.session = MagicMock(name="session")
    stub.DB_NAME = "test_stub"
    stub.__spec__ = ModuleSpec("database.engine", loader=None)
    sys.modules["database.engine"] = stub
    return stub


# The real engine opens MySQL at import time.
ENGINE_STUB = _install_engine_stub()

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

import django  # noqa: E402

django.setup()

import pytest  # noqa: E402
from rest_framework.test import APIRequestFactory, force_authenticate  # noqa: E402

from database.models import (  # noqa: E402
    Brand,
    Employee,
    Job,
    JobStatus,
    Position,
    Role,
    Schedule,
    Shift,
)


class _AuthenticatedUser:
    """Passes IsAuthenticated without touching auth tables."""

    is_authenticated = True
    is_active = True
    is_anonymous = False
    pk = 1

    def __str__(self) -> str:
        """Names the user in DRF output."""
        return "test-user"


@pytest.fixture
def user() -> _AuthenticatedUser:
    """An authenticated principal needing no database."""
    return _AuthenticatedUser()


@pytest.fixture
def factory() -> APIRequestFactory:
    """DRF request factory shared by every test."""
    return APIRequestFactory()


@pytest.fixture
def call(factory, user):
    """Calls a viewset action as an authenticated request."""

    def _call(viewset, methods, verb, path, data=None, **kwargs):
        """Builds the request, authenticates, dispatches it."""
        request = getattr(factory, verb)(path, data, format="json")
        force_authenticate(request, user=user)
        return viewset.as_view(methods)(request, **kwargs)

    return _call


@pytest.fixture
def brand() -> Brand:
    """A real in-memory Brand, safe to dump."""
    return Brand(id=1, name="Aroma", location="Cairo")


@pytest.fixture
def employee() -> Employee:
    """A real in-memory Employee, safe to dump."""
    return Employee(id=7, name="Mona")


@pytest.fixture
def position() -> Position:
    """A real in-memory Position for job payloads."""
    return Position(id=3, name="Cook")


@pytest.fixture
def schedule(brand) -> Schedule:
    """A schedule wired to its brand in memory."""
    row = Schedule(id=4, brand_id=brand.id, starting_date=date(2026, 3, 2))
    row.brand = brand
    return row


@pytest.fixture
def role(schedule) -> Role:
    """A role wired to its schedule in memory."""
    row = Role(id=5, name="Morning Cook", schedule_id=schedule.id)
    row.schedule = schedule
    return row


@pytest.fixture
def job(brand, employee, position) -> Job:
    """An active job joining employee, brand, position."""
    row = Job(
        id=9,
        brand_id=brand.id,
        employee_id=employee.id,
        position_id=position.id,
        status=JobStatus.ACTIVE,
    )
    row.brand, row.employee, row.position = brand, employee, position
    return row


@pytest.fixture
def shift(role, job) -> Shift:
    """A staffed shift with every parent attached."""
    row = Shift(
        id=11,
        job_id=job.id,
        role_id=role.id,
        date=date(2026, 3, 3),
        starting_time=time(8, 0),
        finishing_time=time(16, 0),
    )
    row.role, row.job = role, job
    return row


@pytest.fixture
def unstaffed_shift(role) -> Shift:
    """An empty slot: no job, parents attached."""
    row = Shift(
        id=12,
        job_id=None,
        role_id=role.id,
        date=date(2026, 3, 4),
        starting_time=time(9, 0),
        finishing_time=time(17, 0),
    )
    row.role, row.job = role, None
    return row
