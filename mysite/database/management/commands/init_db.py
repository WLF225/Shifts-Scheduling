"""Create the SQLAlchemy tables.

The project has no Django migrations (the Django ORM is unused), so this is
how the schema gets created. Safe to re-run: create_all skips existing tables.
"""
from django.core.management.base import BaseCommand

from database.engine import engine
from database.models import Base


class Command(BaseCommand):
    help = "Create all SQLAlchemy tables that do not exist yet."

    def handle(self, *args, **options):
        before = set(Base.metadata.tables)
        Base.metadata.create_all(engine)
        self.stdout.write(self.style.SUCCESS(
            f"create_all done for {len(before)} tables: {', '.join(sorted(before))}"
        ))
