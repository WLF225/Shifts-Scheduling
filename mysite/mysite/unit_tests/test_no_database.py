"""Guards the suite against real database access."""
from __future__ import annotations

import socket
from unittest.mock import MagicMock


from mysite.unit_tests.conftest import ENGINE_STUB


def test_engine_module_is_the_stub():
    """The imported engine is our fake module."""
    import database.engine as engine

    assert engine is ENGINE_STUB
    assert isinstance(engine.session, MagicMock)


def test_schemas_bound_to_the_stub_session():
    """Marshmallow schemas never see a real session."""
    from mysite import schemas

    assert schemas.session is ENGINE_STUB.session


def test_repositories_default_to_the_stub_session():
    """Repositories default to the stubbed session."""
    from repositories import base, employee

    assert base.default_session is ENGINE_STUB.session
    assert employee.session is ENGINE_STUB.session


def test_no_real_engine_was_ever_constructed():
    """No SQLAlchemy engine reached a live driver."""
    assert isinstance(ENGINE_STUB.engine, MagicMock)
    assert "pymysql" not in repr(ENGINE_STUB.engine).lower()


def test_a_default_repository_query_hits_the_stub(brand):
    """A default repository queries the fake session."""
    from repositories.brand import BrandRepository

    ENGINE_STUB.session.get.return_value = brand
    repo = BrandRepository()

    assert repo.session is ENGINE_STUB.session
    assert repo.get(1) is brand
    ENGINE_STUB.session.get.assert_called_once()


def test_a_repository_query_opens_no_socket(monkeypatch):
    """Querying dials no network connection."""
    from repositories.brand import BrandRepository

    def _refuse(*args, **kwargs):
        """Fails loudly if anything dials out."""
        raise AssertionError("network connection attempted")

    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)

    assert BrandRepository().get(1) is not None
