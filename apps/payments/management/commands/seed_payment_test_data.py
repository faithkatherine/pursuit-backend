"""
Django management command to seed payment test data.

Creates a complete test environment with users, organizers, events, and config.
Idempotent: safe to run multiple times using get_or_create.

Usage: python manage.py seed_payment_test_data
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.models import PlatformConfig
from apps.events.models import Event
from apps.organizers.models import OrganizerPaymentConfig, OrganizerProfile

User = get_user_model()

PLATFORM_FEE_RATE = Decimal('0.02')


class Command(BaseCommand):
    help = 'Seeds payment test data: users, organizers, events, platform config'

    def handle(self, *args, **options):
        """Execute the seed command."""
        self.stdout.write('\n=== Seeding Payment Test Data ===\n')

        # 1. Create Faith (superuser + organizer)
        faith_user, created = User.objects.get_or_create(
            email='faith@pursuitapp.co.ke',
            defaults={
                'username': 'faith',
                'first_name': 'Faith',
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            }
        )
        if created:
            faith_user.set_password('admin123')
            faith_user.save()
            self.stdout.write(self.style.SUCCESS('✓ Created superuser: faith@pursuitapp.co.ke'))
        else:
            self.stdout.write('  Found existing superuser: faith@pursuitapp.co.ke')

        faith_organizer, created = OrganizerProfile.objects.get_or_create(
            user=faith_user,
            defaults={
                'business_name': 'Pursuit HQ',
                'verified': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('✓ Created organizer profile: Pursuit HQ'))
        else:
            self.stdout.write('  Found existing organizer: Pursuit HQ')

        faith_payment_config, created = OrganizerPaymentConfig.objects.get_or_create(
            organizer=faith_organizer,
            defaults={
                'collection_type': 'paybill',
                'collection_shortcode': '174379',
                'collection_passkey': 'bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919',
                'payout_type': 'b2c',
                'payout_destination': '254712345678',
                'verified': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('✓ Created payment config for Pursuit HQ'))
        else:
            self.stdout.write('  Found existing payment config for Pursuit HQ')

        # 2. Create test organizer
        organizer_user, created = User.objects.get_or_create(
            email='organizer@test.com',
            defaults={
                'username': 'test_organizer',
                'first_name': 'Test',
                'last_name': 'Organizer',
                'is_staff': False,
                'is_superuser': False,
                'is_active': True,
            }
        )
        if created:
            organizer_user.set_password('testpass123')
            organizer_user.save()
            self.stdout.write(self.style.SUCCESS('✓ Created organizer user: organizer@test.com'))
        else:
            self.stdout.write('  Found existing user: organizer@test.com')

        test_organizer, created = OrganizerProfile.objects.get_or_create(
            user=organizer_user,
            defaults={
                'business_name': 'Blanket & Vine',
                'verified': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('✓ Created organizer profile: Blanket & Vine'))
        else:
            self.stdout.write('  Found existing organizer: Blanket & Vine')

        test_payment_config, created = OrganizerPaymentConfig.objects.get_or_create(
            organizer=test_organizer,
            defaults={
                'collection_type': 'paybill',
                'collection_shortcode': '174379',
                'collection_passkey': 'bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919',
                'payout_type': 'b2c',
                'payout_destination': '254712345678',
                'verified': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('✓ Created payment config for Blanket & Vine'))
        else:
            self.stdout.write('  Found existing payment config for Blanket & Vine')

        # 3. Create test consumer user
        buyer_user, created = User.objects.get_or_create(
            email='buyer@test.com',
            defaults={
                'username': 'test_buyer',
                'first_name': 'Test',
                'last_name': 'Buyer',
                'is_staff': False,
                'is_superuser': False,
                'is_active': True,
            }
        )
        if created:
            buyer_user.set_password('testpass123')
            buyer_user.save()
            self.stdout.write(self.style.SUCCESS('✓ Created buyer user: buyer@test.com'))
        else:
            self.stdout.write('  Found existing user: buyer@test.com')

        # 4. Create test events
        default_date = timezone.now() + timezone.timedelta(days=7)
        nairobi_location = Point(-1.286389, 36.817223, srid=4326)

        events_config = [
            {
                'name': '[TEST] Afro Night KES 500',
                'price': Decimal('500.00'),
                'available_tickets': 100,
                'status': 'live',
            },
            {
                'name': '[TEST] Jazz Evening KES 1500',
                'price': Decimal('1500.00'),
                'available_tickets': 50,
                'status': 'live',
            },
            {
                'name': '[TEST] Premium Event KES 3500',
                'price': Decimal('3500.00'),
                'available_tickets': 20,
                'status': 'live',
            },
            {
                'name': '[TEST] Sold Out Event KES 800',
                'price': Decimal('800.00'),
                'available_tickets': 0,
                'status': 'live',
            },
            {
                'name': '[TEST] Free Event',
                'price': Decimal('0.00'),
                'available_tickets': 200,
                'status': 'live',
            },
            {
                'name': '[TEST] Draft Event KES 1000',
                'price': Decimal('1000.00'),
                'available_tickets': 30,
                'status': 'draft',
            },
            {
                'name': '[TEST] Cancelled Event KES 500',
                'price': Decimal('500.00'),
                'available_tickets': 0,
                'status': 'cancelled',
            },
        ]

        for event_config in events_config:
            event, created = Event.objects.get_or_create(
                name=event_config['name'],
                defaults={
                    'organizer': test_organizer,
                    'description': f"Test event: {event_config['name']}",
                    'date': default_date,
                    'price': event_config['price'],
                    'available_tickets': event_config['available_tickets'],
                    'status': event_config['status'],
                    'ticketing_enabled': True,
                    'location': nairobi_location,
                    'location_name': 'Nairobi',
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"✓ Created event: {event_config['name']}"))
            else:
                self.stdout.write(f"  Found existing event: {event_config['name']}")

        # 5. Create PlatformConfig
        platform_config, created = PlatformConfig.objects.get_or_create(
            is_active=True,
            defaults={
                'fee_percentage': Decimal('2.00'),
                'order_expiration_minutes': 15,
                'payout_delay_hours': 24,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('✓ Created PlatformConfig'))
        else:
            self.stdout.write('  Found existing PlatformConfig')

        # Summary
        self.stdout.write('\n=== Seed Summary ===')
        self.stdout.write(f'Users: {User.objects.count()}')
        self.stdout.write(f'Organizers: {OrganizerProfile.objects.count()}')
        self.stdout.write(f'Payment Configs: {OrganizerPaymentConfig.objects.count()}')
        self.stdout.write(f'Events: {Event.objects.filter(name__startswith="[TEST]").count()} test events')
        self.stdout.write(f'Platform Fee: {PLATFORM_FEE_RATE * 100}%')
        self.stdout.write(f'Order Expiration: {platform_config.order_expiration_minutes} minutes')
        self.stdout.write(f'Payout Delay: {platform_config.payout_delay_hours} hours')
        self.stdout.write(self.style.SUCCESS('\n✓ Seed complete!\n'))
