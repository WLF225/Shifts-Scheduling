"""Makes the scoped session per-request."""
from database.engine import session


class DbSessionMiddleware:
    """Removes the session after each request."""

    def __init__(self, get_response):
        """Stores the next handler in the chain."""
        self.get_response = get_response

    def __call__(self, request):
        """Calls the next handler, then removes the session."""
        try:
            return self.get_response(request)
        finally:
            session.remove()
