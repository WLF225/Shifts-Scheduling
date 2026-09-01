"""Resolves ``Authorization: Bearer <access token>`` into ``request.manager``.

Deliberately permissive: an absent or bad token leaves ``request.manager`` as
``None`` rather than rejecting the request, so public routes keep working. The
``@login_required`` decorator in ``authentication.decorators`` is what enforces access.
"""
from authentication.exceptions import InvalidToken
from authentication.tokens import decode_access_token
from repositories.manager import ManagerRepository


def bearer_token(request) -> str | None:
    """Pull the credential out of the Authorization header, if it is a Bearer one."""
    header = request.META.get("HTTP_AUTHORIZATION", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


class BearerAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.manager = None
        request.auth_error = None

        token = bearer_token(request)
        if token:
            try:
                manager_id = decode_access_token(token)
            except InvalidToken as exc:
                request.auth_error = str(exc)
            else:
                manager = ManagerRepository().get(manager_id)
                if manager is not None and manager.is_active:
                    request.manager = manager
                else:
                    request.auth_error = "Account is unavailable"

        return self.get_response(request)
