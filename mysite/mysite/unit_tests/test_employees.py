"""Endpoint tests for both employee mounts."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from components.exceptions import Conflict, NotFound, ValidationError
from mysite.views import EmployeeViewSet


@pytest.fixture
def component():
    """Patches EmployeeComponent as the views see it."""
    with patch("mysite.views.EmployeeComponent") as mocked:
        yield mocked.return_value


def test_list_employees_returns_everyone(call, component, employee):
    """Top-level listing dumps every person."""
    component.list.return_value = [employee]

    response = call(EmployeeViewSet, {"get": "list"}, "get", "/api/v1/employees")

    assert response.status_code == 200
    assert response.data == [{"id": 7, "name": "Mona"}]
    component.list.assert_called_once_with(brand_pk=None)


def test_list_employees_propagates_repository_failure(call, component):
    """A repository blowup answers 500 database error."""
    from repositories.exceptions import RepositoryError

    component.list.side_effect = RepositoryError("connection reset")

    response = call(EmployeeViewSet, {"get": "list"}, "get", "/api/v1/employees")

    assert response.status_code == 500
    assert response.data["detail"] == "Database error"


def test_retrieve_employee_returns_one_person(call, component, employee):
    """Fetches a single employee by id."""
    component.get.return_value = employee

    response = call(
        EmployeeViewSet, {"get": "retrieve"}, "get", "/api/v1/employees/7", pk=7
    )

    assert response.status_code == 200
    assert response.data["name"] == "Mona"


def test_retrieve_missing_employee_is_404(call, component):
    """Unknown employee id answers 404 detail."""
    component.get.side_effect = NotFound("Employee 99 not found")

    response = call(
        EmployeeViewSet, {"get": "retrieve"}, "get", "/api/v1/employees/99", pk=99
    )

    assert response.status_code == 404
    assert response.data == {"detail": "Employee 99 not found"}


def test_create_person_returns_201(call, component, employee):
    """Recording a person answers 201 and the row."""
    component.create_person.return_value = employee

    response = call(
        EmployeeViewSet, {"post": "create"}, "post", "/api/v1/employees", {"name": "Mona"}
    )

    assert response.status_code == 201
    assert response.data == {"id": 7, "name": "Mona"}
    component.employ.assert_not_called()


def test_create_person_without_name_is_400(call, component):
    """A nameless person answers 400 error shape."""
    component.create_person.side_effect = ValidationError("name is required")

    response = call(EmployeeViewSet, {"post": "create"}, "post", "/api/v1/employees", {})

    assert response.status_code == 400
    assert response.data == {"error": "name is required"}


def test_list_brand_employees_scopes_to_the_brand(call, component, employee):
    """Brand mount passes brand_pk down the component."""
    component.list.return_value = [employee]

    response = call(
        EmployeeViewSet,
        {"get": "list"},
        "get",
        "/api/v1/brands/1/employees",
        brand_pk=1,
    )

    assert response.status_code == 200
    component.list.assert_called_once_with(brand_pk=1)


def test_list_brand_employees_for_missing_brand_is_404(call, component):
    """Listing under an unknown brand answers 404."""
    component.list.side_effect = NotFound("Brand 99 not found")

    response = call(
        EmployeeViewSet, {"get": "list"}, "get", "/api/v1/brands/99/employees", brand_pk=99
    )

    assert response.status_code == 404


def test_retrieve_brand_employee_scopes_to_the_brand(call, component, employee):
    """Brand-scoped retrieve forwards both ids."""
    component.get.return_value = employee

    response = call(
        EmployeeViewSet,
        {"get": "retrieve"},
        "get",
        "/api/v1/brands/1/employees/7",
        pk=7,
        brand_pk=1,
    )

    assert response.status_code == 200
    component.get.assert_called_once_with(7, brand_pk=1)


def test_retrieve_brand_employee_not_employed_there_is_404(call, component):
    """A person employed elsewhere answers 404."""
    component.get.side_effect = NotFound("Employee 7 not found at brand 2")

    response = call(
        EmployeeViewSet,
        {"get": "retrieve"},
        "get",
        "/api/v1/brands/2/employees/7",
        pk=7,
        brand_pk=2,
    )

    assert response.status_code == 404


def test_employ_returns_201_with_employee_and_job(call, component, employee, job):
    """Employing answers 201 with both payloads."""
    component.employ.return_value = (employee, job)

    response = call(
        EmployeeViewSet,
        {"post": "create"},
        "post",
        "/api/v1/brands/1/employees",
        {"employee_id": 7, "position_id": 3},
        brand_pk=1,
    )

    assert response.status_code == 201
    assert response.data["employee"] == {"id": 7, "name": "Mona"}
    assert response.data["job"]["role"] == "Cook"
    assert response.data["job"]["status"] == "active"
    component.create_person.assert_not_called()


def test_employ_without_a_position_is_400(call, component):
    """Employing with no position answers 400."""
    component.employ.side_effect = ValidationError("position_id is required")

    response = call(
        EmployeeViewSet,
        {"post": "create"},
        "post",
        "/api/v1/brands/1/employees",
        {"employee_id": 7},
        brand_pk=1,
    )

    assert response.status_code == 400
    assert response.data == {"error": "position_id is required"}


def test_update_employment_returns_the_changed_job(call, component, job):
    """Updating employment answers 200 with the job."""
    component.update_employment.return_value = job

    response = call(
        EmployeeViewSet,
        {"put": "update"},
        "put",
        "/api/v1/brands/1/employees/7",
        {"status": "active"},
        pk=7,
        brand_pk=1,
    )

    assert response.status_code == 200
    assert response.data["job"]["id"] == 9
    assert response.data["employee"]["name"] == "Mona"


def test_update_employment_conflict_is_409(call, component):
    """A colliding employment change answers 409."""
    component.update_employment.side_effect = Conflict("Job already inactive")

    response = call(
        EmployeeViewSet,
        {"put": "update"},
        "put",
        "/api/v1/brands/1/employees/7",
        {"status": "inactive"},
        pk=7,
        brand_pk=1,
    )

    assert response.status_code == 409
    assert response.data == {"detail": "Job already inactive"}
