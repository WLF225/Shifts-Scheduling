"""Framework-free errors raised by components."""


class ComponentError(Exception):
    """Base class for every component failure."""


class ValidationError(ComponentError):
    """The request cannot be honoured as written."""


class NotFound(ComponentError):
    """A thing the caller addressed does not exist."""


class Conflict(ComponentError):
    """The request collides with existing state; a 409."""
