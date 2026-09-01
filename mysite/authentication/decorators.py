"""Route guard for endpoints that require a valid access token."""
from functools import wraps

from django.http import JsonResponse


def login_required(view):
    """Reject the request unless BearerAuthMiddleware resolved a manager."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if getattr(request, "manager", None) is None:
            detail = getattr(request, "auth_error", None) or "Authentication required"
            return JsonResponse({"error": detail}, status=401)
        return view(request, *args, **kwargs)

    return wrapper
