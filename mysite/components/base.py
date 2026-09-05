
from sqlalchemy.orm import Session


class BaseComponent:


    def __init__(self, session: Session | None = None) -> None:
        self.session = session

    def _repo(self, repository_class):
        return repository_class(self.session)
