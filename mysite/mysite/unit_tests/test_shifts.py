"""Endpoint tests for both shift mounts."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from components.exceptions import Conflict, NotFound, ValidationError
from mysite.views import ShiftViewSet

ROLE_PATH = "/api/v1/brands/1/schedules/4/roles/5/shifts"
EMPLOYEE_PATH = "/api/v1/employees/7/shifts"


@pytest.fixture
def component():
    """Patches ShiftComponent as the views see it."""
    with patch("mysite.views.ShiftComponent") as mocked:
        yield mocked.return_value


def test_list_role_shifts_flattens_every_parent(call, component, shift):
    """Role listing flattens role, brand and employee."""
    component.list.return_value = [shift]

    response = call(
        ShiftViewSet,
        {"get": "list"},
        "get",
        ROLE_PATH,
        role_pk=5,
        schedule_pk=4,
        brand_pk=1,
    )

    assert response.status_code == 200
    assert response.data == [
        {
            "shift_id": 11,
            "job_id": 9,
            "employee_id": 7,
            "employee": "Mona",
            "role_id": 5,
            "role": "Morning Cook",
            "schedule_id": 4,
            "brand_id": 1,
            "brand": "Aroma",
            "date": "2026-03-03",
            "starting_time": "08:00:00",
            "finishing_time": "16:00:00",
        }
    ]
    component.list.assert_called_once_with(role_pk=5, employee_pk=None)


def test_list_role_shifts_for_missing_role_is_404(call, component):
    """Listing under an unknown role answers 404."""
    component.list.side_effect = NotFound("Role 99 not found")

    response = call(
        ShiftViewSet,
        {"get": "list"},
        "get",
        "/api/v1/brands/1/schedules/4/roles/99/shifts",
        role_pk=99,
        schedule_pk=4,
        brand_pk=1,
    )

    assert response.status_code == 404
    assert response.data == {"detail": "Role 99 not found"}


def test_retrieve_shift_returns_the_flattened_shift(call, component, shift):
    """Fetches one shift scoped to its parents."""
    component.get.return_value = shift

    response = call(
        ShiftViewSet,
        {"get": "retrieve"},
        "get",
        f"{ROLE_PATH}/11",
        pk=11,
        role_pk=5,
        schedule_pk=4,
        brand_pk=1,
    )

    assert response.status_code == 200
    assert response.data["shift_id"] == 11
    component.get.assert_called_once_with(
        pk=11, role_pk=5, schedule_pk=4, employee_pk=None
    )


def test_retrieve_shift_under_wrong_parent_is_404(call, component):
    """A shift whose parents mismatch answers 404."""
    component.get.side_effect = NotFound("Shift not found")

    response = call(
        ShiftViewSet,
        {"get": "retrieve"},
        "get",
        "/api/v1/brands/1/schedules/4/roles/8/shifts/11",
        pk=11,
        role_pk=8,
        schedule_pk=4,
        brand_pk=1,
    )

    assert response.status_code == 404


def test_create_shift_returns_an_unstaffed_slot(call, component, unstaffed_shift):
    """Creating a slot answers 201 with null staffing."""
    component.create.return_value = unstaffed_shift

    response = call(
        ShiftViewSet,
        {"post": "create"},
        "post",
        ROLE_PATH,
        {"date": "4/3/2026", "starting_time": 9, "finishing_time": 17},
        role_pk=5,
        schedule_pk=4,
        brand_pk=1,
    )

    assert response.status_code == 201
    assert response.data["job_id"] is None
    assert response.data["employee"] is None
    assert response.data["starting_time"] == "09:00:00"


def test_create_shift_outside_the_schedule_week_is_400(call, component):
    """A date outside the week answers 400."""
    component.create.side_effect = ValidationError("date is outside the schedule week")

    response = call(
        ShiftViewSet,
        {"post": "create"},
        "post",
        ROLE_PATH,
        {"date": "1/1/2030", "starting_time": 9, "finishing_time": 17},
        role_pk=5,
        schedule_pk=4,
        brand_pk=1,
    )

    assert response.status_code == 400
    assert response.data == {"error": "date is outside the schedule week"}


def test_create_shift_colliding_with_another_is_409(call, component):
    """A slot clashing with an existing one conflicts."""
    component.create.side_effect = Conflict("Role already has a shift then")

    response = call(
        ShiftViewSet,
        {"post": "create"},
        "post",
        ROLE_PATH,
        {"date": "3/3/2026", "starting_time": 8, "finishing_time": 16},
        role_pk=5,
        schedule_pk=4,
        brand_pk=1,
    )

    assert response.status_code == 409
    assert response.data == {"detail": "Role already has a shift then"}


def test_update_shift_staffs_it(call, component, shift):
    """Staffing a shift answers 200 with the employee."""
    component.update.return_value = shift

    response = call(
        ShiftViewSet,
        {"put": "update"},
        "put",
        f"{ROLE_PATH}/11",
        {"employee_id": 7},
        pk=11,
        role_pk=5,
        schedule_pk=4,
        brand_pk=1,
    )

    assert response.status_code == 200
    assert response.data["employee"] == "Mona"
    component.update.assert_called_once_with(
        {"employee_id": 7}, pk=11, schedule_pk=4, role_pk=5
    )


def test_update_shift_with_mixed_staffing_keys_is_400(call, component):
    """Contradictory staffing keys stay a 400."""
    component.update.side_effect = ValidationError(
        "staffing keys must be all null or all set"
    )

    response = call(
        ShiftViewSet,
        {"put": "update"},
        "put",
        f"{ROLE_PATH}/11",
        {"employee_id": None, "job_id": 7},
        pk=11,
        role_pk=5,
        schedule_pk=4,
        brand_pk=1,
    )

    assert response.status_code == 400
    assert response.data == {"error": "staffing keys must be all null or all set"}


def test_update_shift_for_a_busy_employee_is_409(call, component):
    """Rejects a shift whose employee is busy."""
    component.update.side_effect = Conflict("Employee already booked then")

    response = call(
        ShiftViewSet,
        {"put": "update"},
        "put",
        f"{ROLE_PATH}/11",
        {"employee_id": 7},
        pk=11,
        role_pk=5,
        schedule_pk=4,
        brand_pk=1,
    )

    assert response.status_code == 409
    assert response.data == {"detail": "Employee already booked then"}


def test_list_employee_shifts_reads_one_persons_work(call, component, shift):
    """Employee mount lists that person's shifts."""
    component.list.return_value = [shift]

    response = call(
        ShiftViewSet, {"get": "list"}, "get", EMPLOYEE_PATH, employee_pk=7
    )

    assert response.status_code == 200
    assert response.data[0]["employee_id"] == 7
    component.list.assert_called_once_with(role_pk=None, employee_pk=7)


def test_list_employee_shifts_for_missing_employee_is_404(call, component):
    """Listing for an unknown employee answers 404."""
    component.list.side_effect = NotFound("Employee 99 not found")

    response = call(
        ShiftViewSet, {"get": "list"}, "get", "/api/v1/employees/99/shifts", employee_pk=99
    )

    assert response.status_code == 404


def test_retrieve_employee_shift_scopes_to_the_employee(call, component, shift):
    """Employee-scoped retrieve forwards the employee id."""
    component.get.return_value = shift

    response = call(
        ShiftViewSet,
        {"get": "retrieve"},
        "get",
        f"{EMPLOYEE_PATH}/11",
        pk=11,
        employee_pk=7,
    )

    assert response.status_code == 200
    component.get.assert_called_once_with(
        pk=11, role_pk=None, schedule_pk=None, employee_pk=7
    )


def test_retrieve_shift_of_another_employee_is_404(call, component):
    """Another person's shift answers 404 here."""
    component.get.side_effect = NotFound("Shift not found")

    response = call(
        ShiftViewSet,
        {"get": "retrieve"},
        "get",
        "/api/v1/employees/8/shifts/11",
        pk=11,
        employee_pk=8,
    )

    assert response.status_code == 404
