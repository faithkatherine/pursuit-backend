import os

from django.core.management.base import BaseCommand

from apps.events.models import Event
from apps.events.utils.unsplash import fetch_unsplash_gallery_images, fetch_unsplash_image_url


CATEGORY_SLUGS_BY_NAME = {
    "Concerts & Nightlife": "concerts-and-nightlife",
    "Outdoors & Active": "outdoors-and-active",
    "Food & Drink": "food-and-drink",
    "Culture & Arts": "culture-and-arts",
    "Talks & Ideas": "talks-and-ideas",
    "Workshops & Classes": "workshops-and-classes",
    "Markets & Pop-ups": "markets-and-popups",
    "Travel": "travel",
}


class Command(BaseCommand):
    help = "Backfill Unsplash image URLs for events with no image"

    def handle(self, *args, **options):
        if not os.environ.get("UNSPLASH_ACCESS_KEY"):
            self.stdout.write(
                self.style.WARNING(
                    "UNSPLASH_ACCESS_KEY not set — using fallback images.\n"
                    "Run python manage.py seed_images after adding the key to fetch real images."
                )
            )

        image_count = 0
        gallery_count = 0
        skipped_count = 0
        events = Event.objects.exclude(name__startswith="[TEST]").prefetch_related("category")

        for event in events:
            category = event.category.first()
            category_slug = CATEGORY_SLUGS_BY_NAME.get(category.name) if category else None
            if not category_slug:
                skipped_count += 1
                continue

            update_fields = []
            if not event.image:
                event.image = fetch_unsplash_image_url(category_slug)
                update_fields.append("image")
                image_count += 1
            if event.has_gallery and not event.gallery_images:
                event.gallery_images = fetch_unsplash_gallery_images(category_slug, 3)
                update_fields.append("gallery_images")
                gallery_count += 1
            if update_fields:
                event.save(update_fields=update_fields)

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfilled {image_count} event images and {gallery_count} galleries ({skipped_count} skipped)."
            )
        )
