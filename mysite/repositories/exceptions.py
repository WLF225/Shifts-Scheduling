"""Errors raised by the repository tier.

Deliberately framework-free: nothing here imports Django or DRF, so the data
access tier can be used (and tested) without a web layer. The translation to
HTTP status codes happens once, in ``mysite.exeptions.repository_exception_handler``.
"""


class RepositoryError(Exception):
    """Base class for every repository failure."""


class NotFound(RepositoryError):
    """A row was requested by primary key and does not exist."""

    def __init__(self, model_name, pk):
        self.model_name = model_name
        self.pk = pk
        super().__init__(f"{model_name} {pk} not found")


class InvalidFilter(RepositoryError):
    """A filter or update keyword that is not a column on the model."""
