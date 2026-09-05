"""Endpoint tests for employee busy and free time."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from components.exceptions import NotFound, ValidationError
from mysite.views import EmployeeTimeViewSet

PATH = "/api/v1/employees/7/times"


@pytest.fixture
def component():
    """Patches EmployeeTimeComponent as the views see it."""
    with patch("mysite.views.EmployeeTimeComponent") as mocked:
        yield mocked.return_value


def test_times_returns_busy_and_free_blocks(call, component):
    """Returns both busy blocks and free gaps."""
    component.times.return_value = {
        "employee_id": 7,
        "busy": [{"shift_id": 11, "date": "2026-03-03"}],
        "free": [{"date": "2026-03-03", "starting_time": "16:00:00"}],
    }

    response = call(EmployeeTimeViewSet, {"get": "list"}, "get", PATH, employee_pk=7)

    assert response.status_code == 200
    assert response.data["employee_id"] == 7
    assert response.data["busy"][0]["shift_id"] == 11
    component.times.assert_called_once_with(employee_pk=7, mode=None)


def test_times_forwards_the_mode_query_parameter(call, component):
    """Passes the mode query parameter through."""
    component.times.return_value = {"employee_id": 7, "busy": []}

    response = call(
        EmployeeTimeViewSet, {"get": "list"}, "get", f"{PATH}?mode=busy", employee_pk=7
    )

    assert response.status_code == 200
    component.times.assert_called_once_with(employee_pk=7, mode="busy")


def test_times_for_missing_employee_is_404(call, component):
    """An unknown employee answers 404 detail."""
    component.times.side_effect = NotFound("Employee 99 not found")

    response = call(
        EmployeeTimeViewSet,
        {"get": "list"},
        "get",
        "/api/v1/employees/99/times",
        employee_pk=99,
    )

    assert response.status_code == 404
    assert response.data == {"detail": "Employee 99 not found"}


def test_times_with_an_unknown_mode_is_400(call, component):
    """An unsupported mode answers 400 error shape."""
    component.times.side_effect = ValidationError("mode must be free or busy")

    response = call(
        EmployeeTimeViewSet, {"get": "list"}, "get", f"{PATH}?mode=sleeping", employee_pk=7
    )

    assert response.status_code == 400
    assert response.data == {"error": "mode must be free or busy"}
