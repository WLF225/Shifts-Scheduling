"""Routing contract: deliberately excluded verbs 405."""
from __future__ import annotations

import pytest
from django.urls import Resolver404, resolve
from rest_framework.test import force_authenticate


def _dispatch(factory, user, verb, path, data=None):
    """Resolves a real URL and dispatches the request."""
    match = resolve(path)
    request = getattr(factory, verb)(path, data, format="json")
    force_authenticate(request, user=user)
    return match.func(request, *match.args, **match.kwargs)


def test_put_on_a_top_level_employee_is_405(factory, user):
    """Editing employment needs a brand, so 405."""
    response = _dispatch(factory, user, "put", "/api/v1/employees/7", {"status": "active"})

    assert response.status_code == 405


def test_get_on_a_top_level_employee_still_routes(factory, user):
    """The excluded verb does not remove GET."""
    match = resolve("/api/v1/employees/7")

    assert "get" in match.func.actions
    assert "put" not in match.func.actions


def test_post_on_employee_shifts_is_405(factory, user):
    """A shift write needs a role, so 405."""
    response = _dispatch(
        factory, user, "post", "/api/v1/employees/7/shifts", {"date": "3/3/2026"}
    )

    assert response.status_code == 405


def test_put_on_an_employee_shift_is_405(factory, user):
    """The employee shift mount is read-only."""
    response = _dispatch(
        factory, user, "put", "/api/v1/employees/7/shifts/11", {"employee_id": 7}
    )

    assert response.status_code == 405


def test_role_mount_still_binds_shift_writes(factory, user):
    """The role mount keeps POST and PUT."""
    listing = resolve("/api/v1/brands/1/schedules/4/roles/5/shifts")
    detail = resolve("/api/v1/brands/1/schedules/4/roles/5/shifts/11")

    assert "post" in listing.func.actions
    assert "put" in detail.func.actions


@pytest.mark.parametrize(
    ("path", "url_name"),
    [
        ("/api/v1/brands", "brands-list"),
        ("/api/v1/employees", "employees-list"),
        ("/api/v1/brands/1/schedules", "brand-schedules-list"),
        ("/api/v1/brands/1/schedules/4/roles", "brand-schedule-roles-list"),
        ("/api/v1/employees/7/times", "employee-times-list"),
    ],
)
def test_slashless_spelling_is_the_canonical_route(path, url_name):
    """Slashless paths resolve to the named route."""
    assert resolve(path).url_name == url_name


@pytest.mark.parametrize(
    "path",
    ["/api/v1/brands/", "/api/v1/employees/", "/api/v1/brands/1/schedules/"],
)
def test_the_slashed_spelling_does_not_resolve(path):
    """Trailing-slash spellings are not routed."""
    with pytest.raises(Resolver404):
        resolve(path)
