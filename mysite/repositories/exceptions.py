"""Errors raised by the repository tier.

Deliberately framework-free: nothing here imports Django or DRF, so the data
access tier can be used (and tested) without a web layer. The translation to
HTTP status codes happens once, in ``mysite.exceptions.repository_exception_handler``.
"""


_UNSET = object()
"""Distinguishes "no pk given" from a pk that really is ``None``."""


class RepositoryError(Exception):
    """Base class for every repository failure."""


class NotFound(RepositoryError):
    """A row was requested and does not exist.

    Two spellings, because the two tiers know different things. A repository
    raises ``NotFound(model_name, pk)`` and gets "Employee 7 not found" built
    for it. A view already has the sentence it wants to say - including the
    parent that was searched - so it raises ``NotFound(message)`` and that
    message is used verbatim.

    The HTTP status is *not* an argument: ``repository_exception_handler`` maps
    this class to 404 on its own.
    """

    def __init__(self, model_name, pk=_UNSET):
        self.model_name = model_name
        self.pk = None if pk is _UNSET else pk
        message = (
            model_name if pk is _UNSET else f"{model_name} {pk} not found"
        )
        super().__init__(message)


class InvalidFilter(RepositoryError):
    """A filter or update keyword that is not a column on the model."""
