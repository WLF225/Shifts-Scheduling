"""Endpoint tests for the brands mount."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from components.exceptions import NotFound, ValidationError
from mysite.views import BrandViewSet
from repositories.exceptions import InvalidFilter


@pytest.fixture
def component():
    """Patches BrandComponent as the views see it."""
    with patch("mysite.views.BrandComponent") as mocked:
        yield mocked.return_value


def test_list_brands_returns_every_brand(call, component, brand):
    """Lists brands as a dumped array."""
    component.list.return_value = [brand]

    response = call(BrandViewSet, {"get": "list"}, "get", "/api/v1/brands")

    assert response.status_code == 200
    assert response.data == [{"id": 1, "name": "Aroma", "location": "Cairo"}]


def test_list_brands_survives_an_empty_table(call, component):
    """No brands answers an empty list."""
    component.list.return_value = []

    response = call(BrandViewSet, {"get": "list"}, "get", "/api/v1/brands")

    assert response.status_code == 200
    assert response.data == []


def test_list_brands_with_an_unknown_filter_is_400(call, component):
    """A non-column filter answers 400 invalid_filter."""
    component.list.side_effect = InvalidFilter("colour is not a column")

    response = call(BrandViewSet, {"get": "list"}, "get", "/api/v1/brands?colour=red")

    assert response.status_code == 400
    assert response.data["detail"] == "colour is not a column"


def test_retrieve_brand_returns_one_brand(call, component, brand):
    """Fetches a single brand by id."""
    component.get.return_value = brand

    response = call(BrandViewSet, {"get": "retrieve"}, "get", "/api/v1/brands/1", pk=1)

    assert response.status_code == 200
    assert response.data["name"] == "Aroma"
    component.get.assert_called_once_with(1)


def test_retrieve_missing_brand_is_404(call, component):
    """Unknown brand id answers 404 detail."""
    component.get.side_effect = NotFound("Brand 99 not found")

    response = call(BrandViewSet, {"get": "retrieve"}, "get", "/api/v1/brands/99", pk=99)

    assert response.status_code == 404
    assert response.data == {"detail": "Brand 99 not found"}


def test_create_brand_returns_201(call, component, brand):
    """Creating a brand answers 201 and the row."""
    component.create.return_value = brand

    response = call(
        BrandViewSet,
        {"post": "create"},
        "post",
        "/api/v1/brands",
        {"name": "Aroma", "location": "Cairo"},
    )

    assert response.status_code == 201
    assert response.data["id"] == 1


def test_create_brand_without_name_is_400(call, component):
    """A missing name answers 400 error shape."""
    component.create.side_effect = ValidationError("name is required")

    response = call(
        BrandViewSet, {"post": "create"}, "post", "/api/v1/brands", {"location": "Cairo"}
    )

    assert response.status_code == 400
    assert response.data == {"error": "name is required"}
