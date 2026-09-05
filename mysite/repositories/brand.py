"""Repository for brand rows."""
from database.models import Brand
from repositories.base import BaseRepository


class BrandRepository(BaseRepository[Brand]):
    """Queries over brands."""

    model = Brand
