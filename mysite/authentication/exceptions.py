"""Auth failures, framework-free like ``repositories.exceptions``.

Nothing here imports Django; ``authentication.views`` maps these onto status codes.
"""


class AuthError(Exception):
    """Base class for every authentication failure."""
    status = 401


class InvalidCredentials(AuthError):
    """Username unknown, or password did not match."""

    def __init__(self, message="Invalid username or password"):
        super().__init__(message)


class InvalidToken(AuthError):
    """Token was malformed, expired, revoked, or the wrong type."""


class TokenReuse(AuthError):
    """An already-spent refresh token was presented again."""

    def __init__(self, message="Refresh token has already been used"):
        super().__init__(message)


class InactiveAccount(AuthError):
    """The manager exists but has been deactivated."""
    status = 403

    def __init__(self, message="This account is disabled"):
        super().__init__(message)


class UsernameTaken(AuthError):
    """Registration collided with an existing username or email."""
    status = 409
