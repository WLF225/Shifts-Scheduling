"""Translates domain errors into HTTP responses."""
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
    """DRF exception carrying a caller-chosen status code."""

    def __init__(self, detail=None, code=None, status_code=404):
        """Stores the status code, then defers to APIException."""
        self.status_code = status_code
        super().__init__(detail, code)


def _error_body(exc, context, message):
    """Renders a 400 as {"error": message}."""
    response = drf_exception_handler(DjangoException(message, "error", 400), context)
    if response is not None:
        response.data = {"error": message}
    return response


def repository_exception_handler(exc, context):
    """Maps component and repository errors to statuses."""
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
