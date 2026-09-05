"""Generic repository.

Every query in the project goes through a subclass of :class:`BaseRepository`.
Views ask a repository for objects; they never build a query and never touch the
session themselves.
"""
from __future__ import annotations

from typing import Any, Generic, Sequence, TypeVar

from sqlalchemy import func, inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from database.engine import session as default_session
from database.models import Base
from repositories.exceptions import NotFound, InvalidFilter, RepositoryError

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Read and write access to a single model.

    Subclasses set ``model`` and add the queries specific to that model::

        class ProductRepository(BaseRepository[Products]):
            model = Products

            def low_stock(self, threshold):
                ...

    The session is injected so tests can pass a transaction-scoped session and
    roll it back afterwards; in the app it defaults to the request-scoped
    session from ``database.engine``.
    """

    model: type[ModelT]

    def __init__(self, session: Session | None = None) -> None:
        self.session = session if session is not None else default_session

    # ------------------------------------------------------------------ read

    def get(self, pk: Any) -> ModelT | None:
        """Look a row up by primary key, or ``None``.

        Composite keys are passed as a tuple in column order, e.g.
        ``OrderToProductRepository().get((order_id, product_id))``.
        """
        return self.session.get(self.model, pk)

    def get_or_raise(self, pk: Any) -> ModelT:
        """Like :meth:`get`, but raises :class:`NotFound` instead of returning ``None``."""
        obj = self.get(pk)
        if obj is None:
            raise NotFound(self.model.__name__, pk)
        return obj

    def list(
        self,
        *,
        order_by: Any = None,
        limit: int | None = None,
        offset: int | None = None,
        **filters: Any,
    ) -> Sequence[ModelT]:
        """Return rows matching ``filters``.

        Filter values may be scalars (``customer_id=3``) or collections, which
        become an ``IN`` clause (``category=["food", "clothes"]``).
        """
        return self._all(self._select(order_by=order_by, limit=limit, offset=offset, **filters))

    def first(self, *, order_by: Any = None, **filters: Any) -> ModelT | None:
        """Return the first matching row, or ``None``."""
        return self.session.scalars(self._select(order_by=order_by, limit=1, **filters)).first()

    def exists(self, **filters: Any) -> bool:
        return self.count(**filters) > 0

    def count(self, **filters: Any) -> int:
        stmt = self._apply(select(func.count()).select_from(self.model), filters)
        return self.session.scalar(stmt) or 0

    # ----------------------------------------------------------------- write

    
    def create(self, **values: Any) -> ModelT:
        obj = self.model(**values)
        self.session.add(obj)
        self.commit()
        return obj

    def update(self, instance: ModelT, **values: Any) -> ModelT:
        for key, value in values.items():
            self._column(key)
            setattr(instance, key, value)
        self.commit()
        return instance

    def delete(self, instance: ModelT) -> None:
        self.session.delete(instance)
        self.commit()

    def commit(self) -> None:
        """The only place the session is committed.

        Keeping it in one method means the rollback on failure can never be
        forgotten by a caller.
        """
        try:
            self.session.commit()
        except SQLAlchemyError as exc:
            self.session.rollback()
            raise RepositoryError(str(exc)) from exc

    # ------------------------------------------------------------- internals

    def _select(self, *, order_by=None, limit=None, offset=None, **filters) -> Select:
        stmt = self._apply(select(self.model), filters)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        if offset is not None:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        return stmt

    def _apply(self, stmt: Select, filters: dict[str, Any]) -> Select:
        for key, value in filters.items():
            column = self._column(key)
            if isinstance(value, (list, tuple, set, frozenset)):
                stmt = stmt.where(column.in_(list(value)))
            else:
                stmt = stmt.where(column == value)
        return stmt

    def _column(self, key: str):
        """Resolve a keyword to a real column, so typos fail loudly."""
        if key not in inspect(self.model).columns:
            raise InvalidFilter(f"{self.model.__name__} has no column {key!r}")
        return getattr(self.model, key)

    def _all(self, stmt: Select) -> Sequence[ModelT]:
        return self.session.scalars(stmt).all()
