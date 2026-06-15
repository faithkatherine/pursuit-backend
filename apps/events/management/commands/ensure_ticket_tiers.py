"""
Management command to ensure all events have at least one ticket tier.
Creates a "General Admission" tier for events without any tiers.

Run with: python manage.py ensure_ticket_tiers
"""

from django.core.management.base import BaseCommand

from apps.events.models import Event, TicketTier


class Command(BaseCommand):
    help = "Ensures all events have at least one ticket tier (General Admission)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without actually creating",
        )
        parser.add_argument(
            "--event-id",
            type=int,
            help="Only process a specific event by ID",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        event_id = options.get("event_id")

        if event_id:
            events = Event.objects.filter(id=event_id)
            if not events.exists():
                self.stdout.write(
                    self.style.ERROR(f"Event with ID {event_id} not found")
                )
                return
        else:
            events = Event.objects.all()

        events_without_tiers = []
        for event in events:
            if not event.ticket_tiers.exists():
                events_without_tiers.append(event)

        if not events_without_tiers:
            self.stdout.write(
                self.style.SUCCESS("All events already have ticket tiers!")
            )
            return

        self.stdout.write(
            f"Found {len(events_without_tiers)} event(s) without ticket tiers"
        )

        created_count = 0
        for event in events_without_tiers:
            if dry_run:
                self.stdout.write(
                    f"[DRY RUN] Would create General Admission tier for: {event.name} (ID: {event.id})"
                )
                self.stdout.write(
                    f"  - Price: KES {event.price or 0}"
                )
                self.stdout.write(
                    f"  - Available: {event.available_tickets or 100}"
                )
            else:
                tier = TicketTier.objects.create(
                    event=event,
                    name="General Admission",
                    description="",
                    price=event.price or 0,
                    available=event.available_tickets or 100,
                    capacity=event.available_tickets or 100,
                    is_active=True,
                    sort_order=0,
                )
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Created tier for: {event.name} (ID: {event.id}, Tier ID: {tier.id})"
                    )
                )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\nDry run complete. Would create {len(events_without_tiers)} tier(s)."
                )
            )
            self.stdout.write("Run without --dry-run to apply changes.")
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✓ Successfully created {created_count} General Admission tier(s)!"
                )
            )
