from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler as drf_exception_handler

from components.exceptions import (
    ComponentError,
    Conflict as ComponentConflict,
    NotFound as ComponentNotFound,
    ValidationError as ComponentValidationError,
)
from repositories.exceptions import (
    InvalidFilter,
    NotFound as RepositoryNotFound,
    RepositoryError,
)


class DjangoException(APIException):
    def __init__(self, detail=None, code=None, status_code=404):
        self.status_code = status_code
        super().__init__(detail, code)


def _error_body(exc, context, message):
    """A validation failure as ``{"error": message}``.

    Every 400 in this API used to be built by a ``_bad_request`` helper in
    ``views.py`` that returned exactly this shape, and the viewsets caught
    their own parse errors to call it. The rules moved into the component tier
    and now raise instead, so the response has to be assembled here - and it
    has to keep the same key: DRF's own handler renders ``{"detail": ...}``,
    which would silently change the body of every 400 the clients already
    parse. 404s and 500s are left to DRF, which is where they came from before.
    """
    response = drf_exception_handler(DjangoException(message, "error", 400), context)
    if response is not None:
        response.data = {"error": message}
    return response


def repository_exception_handler(exc, context):
    """Translate component and repository errors into HTTP responses.

    This is the single place the three tiers meet: components and repositories
    raise plain Python exceptions, and the status code is decided here, so no
    view needs a try/except and neither tier below needs to import DRF.

    Component branches come first because a component is the tier that has
    already decided what an outcome *means*. Both packages export a class
    called ``NotFound`` and they are imported under distinct aliases above:
    ``ComponentNotFound`` carries a sentence a component composed - including
    the parents it searched - while ``RepositoryNotFound`` is raised by
    ``get_or_raise`` about a row addressed by pk. Both map to 404 with their
    own message, and ordering them component-first keeps that true even if one
    ever subclasses the other.

    ``ComponentError`` catches anything new in that package that predates a
    branch of its own, as a 400: a component failure is by definition a
    decision about the request, so the caller is the party at fault. That is
    the opposite of the ``RepositoryError`` fallback, which is a 500 with its
    message flattened - a query that failed is this server's problem and its
    text is not for the client to read.

    The two 400 branches go through :func:`_error_body` rather than
    ``DjangoException``, because a 400 has always answered ``{"error": ...}``
    from the old view helper while DRF renders ``{"detail": ...}``. Every other
    status keeps the shape DRF already gave it.
    """
    if isinstance(exc, ComponentNotFound):
        exc = DjangoException(str(exc), "not_found", 404)
    elif isinstance(exc, ComponentValidationError):
        return _error_body(exc, context, str(exc))
    elif isinstance(exc, ComponentConflict):
        exc = DjangoException(str(exc), "conflict", 409)
    elif isinstance(exc, ComponentError):
        return _error_body(exc, context, str(exc))
    elif isinstance(exc, RepositoryNotFound):
        exc = DjangoException(str(exc), "not_found", 404)
    elif isinstance(exc, InvalidFilter):
        exc = DjangoException(str(exc), "invalid_filter", 400)
    elif isinstance(exc, RepositoryError):
        exc = DjangoException("Database error", "db_error", 500)
    return drf_exception_handler(exc, context)
