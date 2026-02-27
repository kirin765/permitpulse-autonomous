from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand

from permitpulse.services.ingestion import ingest_city_rules


class Command(BaseCommand):
    help = "Runs one full data loop: fetch -> parse -> validate -> publish"

    def handle(self, *args, **options):
        for city_code in settings.PERMITPULSE_CITY_CODES:
            snapshot = ingest_city_rules(city_code)
            self.stdout.write(self.style.SUCCESS(f"{city_code}: snapshot={getattr(snapshot, 'id', None)}"))
