"""Endpoint tests for brand-nested schedules."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from components.exceptions import NotFound, ValidationError
from mysite.views import ScheduleViewSet


@pytest.fixture
def component():
    """Patches ScheduleComponent as the views see it."""
    with patch("mysite.views.ScheduleComponent") as mocked:
        yield mocked.return_value


def test_list_schedules_returns_one_brands_weeks(call, component, schedule):
    """Lists the schedules belonging to a brand."""
    component.list.return_value = [schedule]

    response = call(
        ScheduleViewSet, {"get": "list"}, "get", "/api/v1/brands/1/schedules", brand_pk=1
    )

    assert response.status_code == 200
    assert response.data[0]["id"] == 4
    assert response.data[0]["starting_date"] == "2026-03-02"
    component.list.assert_called_once_with(brand_pk=1)


def test_list_schedules_for_missing_brand_is_404(call, component):
    """Listing under an unknown brand answers 404."""
    component.list.side_effect = NotFound("Brand 99 not found")

    response = call(
        ScheduleViewSet,
        {"get": "list"},
        "get",
        "/api/v1/brands/99/schedules",
        brand_pk=99,
    )

    assert response.status_code == 404
    assert response.data == {"detail": "Brand 99 not found"}


def test_retrieve_schedule_returns_one_week(call, component, schedule):
    """Fetches a schedule scoped to its brand."""
    component.get.return_value = schedule

    response = call(
        ScheduleViewSet,
        {"get": "retrieve"},
        "get",
        "/api/v1/brands/1/schedules/4",
        pk=4,
        brand_pk=1,
    )

    assert response.status_code == 200
    assert response.data["brand_id"] == 1
    component.get.assert_called_once_with(pk=4, brand_pk=1)


def test_retrieve_schedule_of_another_brand_is_404(call, component):
    """Cross-brand schedule access answers 404."""
    component.get.side_effect = NotFound("Schedule 4 not found for brand 2")

    response = call(
        ScheduleViewSet,
        {"get": "retrieve"},
        "get",
        "/api/v1/brands/2/schedules/4",
        pk=4,
        brand_pk=2,
    )

    assert response.status_code == 404


def test_create_schedule_returns_201(call, component, schedule):
    """Opening a schedule week answers 201."""
    component.create.return_value = schedule

    response = call(
        ScheduleViewSet,
        {"post": "create"},
        "post",
        "/api/v1/brands/1/schedules",
        {"starting_date": "2/3/2026"},
        brand_pk=1,
    )

    assert response.status_code == 201
    assert response.data["starting_date"] == "2026-03-02"


def test_create_schedule_with_bad_date_is_400(call, component):
    """An unparseable date answers 400 error shape."""
    component.create.side_effect = ValidationError("starting_date is not a date")

    response = call(
        ScheduleViewSet,
        {"post": "create"},
        "post",
        "/api/v1/brands/1/schedules",
        {"starting_date": "not-a-date"},
        brand_pk=1,
    )

    assert response.status_code == 400
    assert response.data == {"error": "starting_date is not a date"}
