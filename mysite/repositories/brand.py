from database.models import Brand
from repositories.base import BaseRepository


class BrandRepository(BaseRepository[Brand]):
    model = Brand
