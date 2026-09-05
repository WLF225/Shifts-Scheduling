"""Business rules for brands."""
from __future__ import annotations

from typing import Any, Sequence

from components.base import BaseComponent
from components.exceptions import NotFound
from components.parsing import body_dict, pick, require_text
from database.models import Brand
from repositories.brand import BrandRepository

class BrandComponent(BaseComponent):
    """Reads and creates brands."""

    def get(self, pk) -> Brand:
        """One brand by id, or 404."""
        brand = self._repo(BrandRepository).get(pk)
        if brand is None:
            raise NotFound("Brand not found")
        return brand

    def list(self) -> Sequence[Brand]:
        """Every brand."""
        return self._repo(BrandRepository).list()

    def create(self, data: Any) -> Brand:
        """Create a brand; name and location are required."""
        body = body_dict(data)
        name = require_text(pick(body, "name"), "name")
        location = require_text(pick(body, "location"), "location", 255)
        return self._repo(BrandRepository).create(name=name, location=location)

    def require(self, pk) -> Brand:
        """The brand a child write hangs off."""
        brand = self._repo(BrandRepository).get(pk)
        if brand is None:
            raise NotFound(f"Brand {pk} not found")
        return brand
