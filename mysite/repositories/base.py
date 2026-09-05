"""The only place queries are built."""
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
    """Read and write access to a single model."""

    model: type[ModelT]

    def __init__(self, session: Session | None = None) -> None:
        """Uses the injected session, else the scoped one."""
        self.session = session if session is not None else default_session

    def get(self, pk: Any) -> ModelT | None:
        """A row by primary key, or None."""
        return self.session.get(self.model, pk)

    def get_or_raise(self, pk: Any) -> ModelT:
        """A row by primary key, or raises NotFound."""
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
        """Rows matching every filter, scalars or collections."""
        return self._all(self._select(order_by=order_by, limit=limit, offset=offset, **filters))

    def first(self, *, order_by: Any = None, **filters: Any) -> ModelT | None:
        """The first matching row, or None."""
        return self.session.scalars(self._select(order_by=order_by, limit=1, **filters)).first()

    def exists(self, **filters: Any) -> bool:
        """True when at least one row matches."""
        return self.count(**filters) > 0

    def count(self, **filters: Any) -> int:
        """How many rows match the filters."""
        stmt = self._apply(select(func.count()).select_from(self.model), filters)
        return self.session.scalar(stmt) or 0

    # ----------------------------------------------------------------- write

    
    def create(self, **values: Any) -> ModelT:
        """Adds a new row and commits it."""
        obj = self.model(**values)
        self.session.add(obj)
        self.commit()
        return obj

    def update(self, instance: ModelT, **values: Any) -> ModelT:
        """Sets the given columns and commits."""
        for key, value in values.items():
            self._column(key)
            setattr(instance, key, value)
        self.commit()
        return instance

    def delete(self, instance: ModelT) -> None:
        """Deletes the row and commits."""
        self.session.delete(instance)
        self.commit()

    def commit(self) -> None:
        """Commits, rolling back and raising on failure."""
        try:
            self.session.commit()
        except SQLAlchemyError as exc:
            self.session.rollback()
            raise RepositoryError(str(exc)) from exc

    def _select(self, *, order_by=None, limit=None, offset=None, **filters) -> Select:
        """Builds a SELECT with filters, order, limit, offset."""
        stmt = self._apply(select(self.model), filters)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        if offset is not None:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        return stmt

    def _apply(self, stmt: Select, filters: dict[str, Any]) -> Select:
        """Adds one WHERE clause per filter keyword."""
        for key, value in filters.items():
            column = self._column(key)
            if isinstance(value, (list, tuple, set, frozenset)):
                stmt = stmt.where(column.in_(list(value)))
            else:
                stmt = stmt.where(column == value)
        return stmt

    def _column(self, key: str):
        """Resolves a keyword to a column, rejecting typos."""
        if key not in inspect(self.model).columns:
            raise InvalidFilter(f"{self.model.__name__} has no column {key!r}")
        return getattr(self.model, key)

    def _all(self, stmt: Select) -> Sequence[ModelT]:
        """Runs the statement and returns every row."""
        return self.session.scalars(stmt).all()
