"""Framework-free errors raised by repositories."""


_UNSET = object()
"""Distinguishes no pk given from pk None."""


class RepositoryError(Exception):
    """Base class for every repository failure."""


class NotFound(RepositoryError):
    """A requested row does not exist."""

    def __init__(self, model_name, pk=_UNSET):
        """Builds the message from model name and pk."""
        self.model_name = model_name
        self.pk = None if pk is _UNSET else pk
        message = (
            model_name if pk is _UNSET else f"{model_name} {pk} not found"
        )
        super().__init__(message)


class InvalidFilter(RepositoryError):
    """A keyword that is not a model column."""
