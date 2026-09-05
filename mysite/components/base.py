"""Shared base for the component tier."""

from sqlalchemy.orm import Session


class BaseComponent:
    """Holds a session and builds repositories from it."""

    def __init__(self, session: Session | None = None) -> None:
        """Store the session; None means the shared one."""
        self.session = session

    def _repo(self, repository_class):
        """Build a repository bound to this component's session."""
        return repository_class(self.session)
