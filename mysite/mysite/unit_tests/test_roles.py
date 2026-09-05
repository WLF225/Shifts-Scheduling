"""Endpoint tests for schedule-nested roles."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from components.exceptions import NotFound, ValidationError
from mysite.views import RoleViewSet

PATH = "/api/v1/brands/1/schedules/4/roles"


@pytest.fixture
def component():
    """Patches RoleComponent as the views see it."""
    with patch("mysite.views.RoleComponent") as mocked:
        yield mocked.return_value


def test_list_roles_returns_one_schedules_roles(call, component, role):
    """Lists the roles under one schedule."""
    component.list.return_value = [role]

    response = call(
        RoleViewSet, {"get": "list"}, "get", PATH, schedule_pk=4, brand_pk=1
    )

    assert response.status_code == 200
    assert response.data == [
        {"id": 5, "name": "Morning Cook", "schedule_id": 4}
    ]
    component.list.assert_called_once_with(schedule_pk=4)


def test_list_roles_for_missing_schedule_is_404(call, component):
    """Listing under an unknown schedule answers 404."""
    component.list.side_effect = NotFound("Schedule 99 not found")

    response = call(
        RoleViewSet,
        {"get": "list"},
        "get",
        "/api/v1/brands/1/schedules/99/roles",
        schedule_pk=99,
        brand_pk=1,
    )

    assert response.status_code == 404
    assert response.data == {"detail": "Schedule 99 not found"}


def test_retrieve_role_returns_one_role(call, component, role):
    """Fetches a role scoped to its schedule."""
    component.get.return_value = role

    response = call(
        RoleViewSet,
        {"get": "retrieve"},
        "get",
        f"{PATH}/5",
        pk=5,
        schedule_pk=4,
        brand_pk=1,
    )

    assert response.status_code == 200
    assert response.data["name"] == "Morning Cook"
    component.get.assert_called_once_with(pk=5, schedule_pk=4)


def test_retrieve_role_of_another_schedule_is_404(call, component):
    """A role under a different schedule answers 404."""
    component.get.side_effect = NotFound("Role 5 not found for schedule 8")

    response = call(
        RoleViewSet,
        {"get": "retrieve"},
        "get",
        "/api/v1/brands/1/schedules/8/roles/5",
        pk=5,
        schedule_pk=8,
        brand_pk=1,
    )

    assert response.status_code == 404


def test_create_role_returns_201(call, component, role):
    """Adding a role to a schedule answers 201."""
    component.create.return_value = role

    response = call(
        RoleViewSet,
        {"post": "create"},
        "post",
        PATH,
        {"name": "Morning Cook"},
        schedule_pk=4,
        brand_pk=1,
    )

    assert response.status_code == 201
    assert response.data["schedule_id"] == 4
    component.create.assert_called_once_with(
        {"name": "Morning Cook"}, schedule_pk=4, brand_pk=1
    )


def test_create_role_without_name_is_400(call, component):
    """A nameless role answers 400 error shape."""
    component.create.side_effect = ValidationError("name is required")

    response = call(
        RoleViewSet,
        {"post": "create"},
        "post",
        PATH,
        {},
        schedule_pk=4,
        brand_pk=1,
    )

    assert response.status_code == 400
    assert response.data == {"error": "name is required"}
