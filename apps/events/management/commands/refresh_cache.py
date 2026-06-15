"""
Management command to manually refresh the events cache.
Run with: python manage.py refresh_cache
"""

from django.core.cache import cache
from django.core.management.base import BaseCommand

from apps.events.signals import EVENTS_CACHE_VERSION_KEY


class Command(BaseCommand):
    help = "Manually increment events cache version to invalidate all cached queries"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear-all",
            action="store_true",
            help="Clear all cache (not just increment version)",
        )

    def handle(self, *args, **options):
        if options["clear_all"]:
            try:
                cache.clear()
                self.stdout.write(self.style.SUCCESS("✓ Cleared all cache"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to clear cache: {e}"))
        else:
            try:
                old_version = cache.get(EVENTS_CACHE_VERSION_KEY, 0)
                cache.incr(EVENTS_CACHE_VERSION_KEY)
                new_version = cache.get(EVENTS_CACHE_VERSION_KEY)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Events cache version: {old_version} → {new_version}"
                    )
                )
                self.stdout.write(
                    "All event queries will now fetch fresh data from the database."
                )
            except ValueError:
                cache.set(EVENTS_CACHE_VERSION_KEY, 1)
                self.stdout.write(
                    self.style.SUCCESS("✓ Events cache version initialized to 1")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Failed to increment cache version: {e}")
                )
