from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler as drf_exception_handler

from repositories.exceptions import InvalidFilter, NotFound, RepositoryError


class DjangoException(APIException):
    def __init__(self, detail=None, code=None, status_code=404):
        self.status_code = status_code
        super().__init__(detail, code)


def repository_exception_handler(exc, context):
    """Translate repository errors into HTTP responses.

    This is the single place the two tiers meet: repositories raise plain
    Python exceptions, and the status code is decided here, so no view needs a
    try/except and no repository needs to import DRF.
    """
    if isinstance(exc, NotFound):
        exc = DjangoException(str(exc), "not_found", 404)
    elif isinstance(exc, InvalidFilter):
        exc = DjangoException(str(exc), "invalid_filter", 400)
    elif isinstance(exc, RepositoryError):
        exc = DjangoException("Database error", "db_error", 500)
    return drf_exception_handler(exc, context)
