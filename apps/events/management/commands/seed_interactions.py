import random

from django.core.management.base import BaseCommand

from apps.events.models import Event, UserEvents
from apps.users.models import User

MOCK_USERS = [
    ("Amara", "Okafor", "amara.okafor@mock.test"),
    ("Liam", "Nakamura", "liam.nakamura@mock.test"),
    ("Fatima", "Al-Rashid", "fatima.alrashid@mock.test"),
    ("Carlos", "Mendez", "carlos.mendez@mock.test"),
    ("Priya", "Sharma", "priya.sharma@mock.test"),
    ("Kwame", "Asante", "kwame.asante@mock.test"),
    ("Sofia", "Petrov", "sofia.petrov@mock.test"),
    ("James", "Mwangi", "james.mwangi@mock.test"),
    ("Yuki", "Tanaka", "yuki.tanaka@mock.test"),
    ("Nia", "Johnson", "nia.johnson@mock.test"),
]

MOCK_EMAIL_DOMAIN = "@mock.test"


class Command(BaseCommand):
    help = "Seed mock user interactions (saves) to generate trending data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete mock users and their interactions before seeding",
        )

    def handle(self, *args, **options):
        if options["flush"]:
            mock_users = User.objects.filter(email__endswith=MOCK_EMAIL_DOMAIN)
            count = mock_users.count()
            mock_users.delete()
            self.stdout.write(self.style.WARNING(
                f"Deleted {count} mock users and their interactions."
            ))
            return

        events = list(Event.objects.filter(is_active=True).order_by("id"))
        if not events:
            self.stderr.write(self.style.ERROR(
                "No events found. Run seed_events first."
            ))
            return

        # Create mock users
        users = []
        for first, last, email in MOCK_USERS:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "username": email,
                },
            )
            if created:
                user.set_password("mock-password-123")
                user.save()
            users.append(user)

        # Weight distribution: first ~10 events get 3x weight to create trending
        trending_pool = events[:10]
        normal_pool = events[10:]
        weighted_events = trending_pool * 3 + normal_pool

        created_count = 0
        skipped_count = 0

        for user in users:
            num_saves = random.randint(5, 15)
            chosen = random.sample(
                weighted_events,
                min(num_saves, len(weighted_events)),
            )
            # Deduplicate
            seen = set()
            unique_choices = []
            for e in chosen:
                if e.id not in seen:
                    seen.add(e.id)
                    unique_choices.append(e)

            for event in unique_choices:
                _, created = UserEvents.objects.get_or_create(
                    user=user, event=event,
                )
                if created:
                    created_count += 1
                else:
                    skipped_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Created {created_count} interactions "
            f"({skipped_count} already existed) "
            f"across {len(users)} mock users."
        ))
