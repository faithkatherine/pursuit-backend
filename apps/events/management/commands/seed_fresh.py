"""
Flush and reseed all event data with realistic Nairobi events.
Preserves users but recreates events, interactions, trips, and editor's picks.

Usage: python manage.py seed_fresh
"""

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import Category
from apps.events.models import EditorsPick, Event, EventGoing, TicketTier, UserEvents
from apps.events.utils.unsplash import (
    fetch_unsplash_gallery_images,
    fetch_unsplash_image_url,
)
from apps.itinerary.models import Trip
from apps.organizers.models import OrganizerProfile
from apps.users.models import User


class Command(BaseCommand):
    help = "Flush and reseed all event data with diverse realistic events"

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("\n🗑️  Flushing existing data (preserving users)...\n"))

        with transaction.atomic():
            # Flush event-related data in correct order (respecting foreign key constraints)
            # Delete in order: dependent objects first, then what they depend on
            UserEvents.objects.all().delete()
            EventGoing.objects.all().delete()
            EditorsPick.objects.all().delete()
            Trip.objects.all().delete()

            # Delete orders/tickets before events and ticket tiers (due to PROTECT constraints)
            from apps.tickets.models import Ticket
            from apps.payments.models import MPESATransaction, OrderItem, Order
            from apps.organizers.models import OrganizerPayout

            # Delete payouts first (they reference orders with PROTECT)
            OrganizerPayout.objects.all().delete()

            # Then delete tickets, orders, and related
            Ticket.objects.all().delete()
            MPESATransaction.objects.all().delete()
            OrderItem.objects.all().delete()
            Order.objects.all().delete()

            # Now safe to delete ticket tiers and events
            TicketTier.objects.all().delete()
            Event.objects.all().delete()
            Category.objects.all().delete()

            self.stdout.write(self.style.SUCCESS("✓ Flushed all event data\n"))

            # Seed organizers
            self.stdout.write("👤 Creating organizers...")
            organizers = self._seed_organizers()
            self.stdout.write(self.style.SUCCESS(f"✓ Created {len(organizers)} organizers\n"))

            # Seed users
            self.stdout.write("👥 Creating users...")
            user_count = self._seed_users()
            self.stdout.write(self.style.SUCCESS(f"✓ Created/verified {user_count} users\n"))

            # Seed categories
            self.stdout.write("📂 Creating categories...")
            categories = self._seed_categories()
            self.stdout.write(self.style.SUCCESS(f"✓ Created {len(categories)} categories\n"))

            # Seed events
            self.stdout.write("🎉 Creating events...")
            events = self._seed_events(categories, organizers)
            self.stdout.write(self.style.SUCCESS(f"✓ Created {len(events)} events\n"))

            # Seed ticket tiers
            self.stdout.write("🎫 Creating ticket tiers...")
            tiers_count = self._seed_ticket_tiers(events)
            self.stdout.write(self.style.SUCCESS(f"✓ Created {tiers_count} ticket tiers\n"))

            # Seed user interactions
            self.stdout.write("❤️  Creating user interactions...")
            interaction_count = self._seed_user_interactions(events)
            self.stdout.write(self.style.SUCCESS(f"✓ Created {interaction_count} user interactions\n"))

            # Seed editor's picks
            self.stdout.write("⭐ Creating editor's picks...")
            picks_count = self._seed_editors_picks(events)
            self.stdout.write(self.style.SUCCESS(f"✓ Created {picks_count} editor's picks\n"))

            # # Trips feature temporarily removed — seed commented out
            # # TODO: re-enable when trips feature is restored
            # self.stdout.write("✈️  Creating trips...")
            # trips_count = self._seed_trips(events)
            # self.stdout.write(self.style.SUCCESS(f"✓ Created {trips_count} trips\n"))

            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✅ Seed complete: {len(events)} events, {interaction_count} interactions, {picks_count} picks\n"
                )
            )

    def _seed_organizers(self):
        """Create 5 internal Pursuit organizers with realistic Nairobi names"""
        organizers_data = [
            {
                "email": "skybar@pursuitapp.co.ke",
                "first_name": "Sky",
                "last_name": "Lounge",
                "business_name": "Rooftop Nairobi",
                "description": "Elevated experiences in the heart of Westlands. Premium rooftop venue for live music, sundowners, and private events.",
                "website_url": "https://rooftopnairobi.co.ke",
                "contact_email": "events@rooftopnairobi.co.ke",
            },
            {
                "email": "artcollective@pursuitapp.co.ke",
                "first_name": "Nairobi",
                "last_name": "Arts",
                "business_name": "The Creative Hive",
                "description": "Contemporary arts collective showcasing emerging East African talent through exhibitions, workshops, and cultural events.",
                "contact_email": "hello@creativehive.co.ke",
            },
            {
                "email": "wellness@pursuitapp.co.ke",
                "first_name": "Zen",
                "last_name": "Studios",
                "business_name": "Movement & Mindfulness Studio",
                "description": "Holistic wellness space offering yoga, pilates, meditation, and fitness classes in Karen.",
                "website_url": "https://movementmindfulness.co.ke",
                "contact_email": "studio@movementmindfulness.co.ke",
            },
            {
                "email": "techcommunity@pursuitapp.co.ke",
                "first_name": "Tech",
                "last_name": "Nairobi",
                "business_name": "Nairobi Tech Collective",
                "description": "Community-driven tech events, hackathons, and networking for developers, founders, and innovators.",
                "contact_email": "connect@nairotechcollective.org",
            },
            {
                "email": "foodevents@pursuitapp.co.ke",
                "first_name": "Flavor",
                "last_name": "Events",
                "business_name": "Nairobi Flavor Co.",
                "description": "Curating unforgettable food and dining experiences — from street food festivals to fine dining pop-ups.",
                "website_url": "https://nairobiflavorco.com",
                "contact_email": "bookings@nairobiflavorco.com",
            },
        ]

        organizers = []
        for org_data in organizers_data:
            user, _ = User.objects.get_or_create(
                email=org_data["email"],
                defaults={
                    "first_name": org_data["first_name"],
                    "last_name": org_data["last_name"],
                    "is_active": True,
                    "username": org_data["email"].split("@")[0],
                }
            )

            organizer, _ = OrganizerProfile.objects.get_or_create(
                user=user,
                defaults={
                    "business_name": org_data["business_name"],
                    "description": org_data.get("description", ""),
                    "website_url": org_data.get("website_url", ""),
                    "contact_email": org_data.get("contact_email", ""),
                    "verified": True,
                }
            )
            organizers.append(organizer)

        return organizers

    def _seed_users(self):
        """Create 18 users with realistic Nairobi names"""
        users_data = [
            # Special user - must exist and have most interactions
            {"email": "faithcathy12@gmail.com", "first_name": "Faith", "last_name": "Catherine"},
            # Additional users with realistic Kenyan names
            {"email": "kamau.njoroge@gmail.com", "first_name": "Kamau", "last_name": "Njoroge"},
            {"email": "wanjiru.kariuki@outlook.com", "first_name": "Wanjiru", "last_name": "Kariuki"},
            {"email": "brian.otieno@gmail.com", "first_name": "Brian", "last_name": "Otieno"},
            {"email": "amina.hassan@gmail.com", "first_name": "Amina", "last_name": "Hassan"},
            {"email": "dennis.kiprop@outlook.com", "first_name": "Dennis", "last_name": "Kiprop"},
            {"email": "mercy.achieng@gmail.com", "first_name": "Mercy", "last_name": "Achieng"},
            {"email": "kevin.mwangi@gmail.com", "first_name": "Kevin", "last_name": "Mwangi"},
            {"email": "rachel.wambui@outlook.com", "first_name": "Rachel", "last_name": "Wambui"},
            {"email": "john.omondi@gmail.com", "first_name": "John", "last_name": "Omondi"},
            {"email": "esther.njeri@gmail.com", "first_name": "Esther", "last_name": "Njeri"},
            {"email": "alex.kimani@outlook.com", "first_name": "Alex", "last_name": "Kimani"},
            {"email": "grace.wanjiku@gmail.com", "first_name": "Grace", "last_name": "Wanjiku"},
            {"email": "steve.ochieng@gmail.com", "first_name": "Steve", "last_name": "Ochieng"},
            {"email": "naomi.chebet@outlook.com", "first_name": "Naomi", "last_name": "Chebet"},
            {"email": "victor.mutua@gmail.com", "first_name": "Victor", "last_name": "Mutua"},
            {"email": "linda.adhiambo@gmail.com", "first_name": "Linda", "last_name": "Adhiambo"},
            {"email": "mark.kimutai@outlook.com", "first_name": "Mark", "last_name": "Kimutai"},
        ]

        for user_data in users_data:
            User.objects.get_or_create(
                email=user_data["email"],
                defaults={
                    "first_name": user_data["first_name"],
                    "last_name": user_data.get("last_name", ""),
                    "is_active": True,
                    "username": user_data["email"].split("@")[0],
                }
            )

        return len(users_data)

    def _seed_categories(self):
        """Create the 8 core categories"""
        category_map = {
            "concerts-and-nightlife": {"name": "Concerts & Nightlife", "icon": "🎵", "color": "#1a1a2e"},
            "outdoors-and-active": {"name": "Outdoors & Active", "icon": "🏃", "color": "#59904a"},
            "food-and-drink": {"name": "Food & Drink", "icon": "🍽️", "color": "#d4622a"},
            "culture-and-arts": {"name": "Culture & Arts", "icon": "🎨", "color": "#8b7fbc"},
            "talks-and-ideas": {"name": "Talks & Ideas", "icon": "💡", "color": "#966a59"},
            "workshops-and-classes": {"name": "Workshops & Classes", "icon": "✏️", "color": "#a67256"},
            "markets-and-popups": {"name": "Markets & Popups", "icon": "🛍️", "color": "#d4b85a"},
            "travel": {"name": "Travel", "icon": "✈️", "color": "#4a6b8a"},
        }

        categories = {}
        for slug, data in category_map.items():
            cat, _ = Category.objects.get_or_create(name=data["name"], defaults=data)
            categories[slug] = cat

        return categories

    def _seed_events(self, categories, organizers):
        """
        Create 50+ diverse events across 4 event types:
        - Type A: Internal organizer, Free (ticketing_enabled=False)
        - Type B: Internal organizer, Paid (ticketing_enabled=True)
        - Type C: External organizer, Free (ticketing_enabled=False, has more_details_url)
        - Type D: External organizer, Paid (ticketing_enabled=False, has more_details_url)
        """
        nairobi_tz = ZoneInfo("Africa/Nairobi")
        now = timezone.now().astimezone(nairobi_tz)

        import random
        random.seed(42)  # Deterministic for reproducibility

        events_data = [
            # TYPE A: Internal, Free — 15 events
            {
                "name": "Sunday Morning Yoga in the Park",
                "description": "Free community yoga session at Uhuru Park. All levels welcome. Bring your own mat and water. We meet near the central fountain at 7am sharp. Great way to start your Sunday with mindfulness and movement.",
                "category": "outdoors-and-active",
                "venue": "Uhuru Park",
                "location_tag": "nairobi",
                "lat": -1.2833,
                "lng": 36.8172,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 42,
                "event_type": "A",
                "start_offset_hours": -120,  # Past event
                "duration_hours": 2,
            },
            {
                "name": "Open Mic Night at Alchemist",
                "description": "Free entry open mic for poets, comedians, and musicians. Sign up at 7pm, show starts at 8pm. Drink minimum KES 500. Supportive crowd, all levels of experience welcome. The back tables have the best acoustics.",
                "category": "culture-and-arts",
                "venue": "Alchemist Bar",
                "location_tag": "nairobi",
                "lat": -1.2673,
                "lng": 36.8073,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 38,
                "event_type": "A",
                "start_offset_hours": 5,  # Tonight
                "duration_hours": 4,
            },
            {
                "name": "Parkrun Nairobi: 5K Saturday Run",
                "description": "Free weekly 5K timed run at Karura Forest. All abilities welcome. Register online before your first run. Kids' 2K starts at 8am. Arrive with your barcode by 8:45am — registration desk closes at 9am sharp.",
                "category": "outdoors-and-active",
                "venue": "Karura Forest",
                "location_tag": "nairobi",
                "lat": -1.2404,
                "lng": 36.8394,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 187,
                "event_type": "A",
                "start_offset_hours": 72,  # This weekend
                "duration_hours": 2,
                "series_name": "Parkrun Nairobi",
            },
            {
                "name": "Community Art Exhibition Opening Night",
                "description": "Free opening reception for local artists' exhibition. Wine and light bites served. Meet the artists, enjoy the work, and support the Nairobi creative community. Exhibition runs for 2 weeks after opening.",
                "category": "culture-and-arts",
                "venue": "GoDown Arts Centre",
                "location_tag": "nairobi",
                "lat": -1.2699,
                "lng": 36.8387,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 94,
                "event_type": "A",
                "start_offset_hours": 168,  # Next week
                "duration_hours": 3,
            },
            {
                "name": "Tech Meetup: AI & Machine Learning",
                "description": "Free monthly tech meetup for developers and data scientists. This month: practical applications of AI in Kenyan startups. Networking, pizza, and drinks included. Bring your laptop if you want to follow along with the live demo.",
                "category": "talks-and-ideas",
                "venue": "PAWA254",
                "location_tag": "nairobi",
                "lat": -1.3152,
                "lng": 36.8322,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 78,
                "event_type": "A",
                "start_offset_hours": -240,  # Past event
                "duration_hours": 3,
            },
            {
                "name": "Farmers Market at Spring Valley",
                "description": "Free entry to weekly farmers market. Organic produce, homemade jams, fresh bread, honey, and crafts. Live music and food trucks. Arrive early — best produce sells out by 10am during peak season.",
                "category": "markets-and-popups",
                "venue": "Spring Valley Community Market",
                "location_tag": "nairobi",
                "lat": -1.2642,
                "lng": 36.7886,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 156,
                "event_type": "A",
                "start_offset_hours": 96,  # This weekend
                "duration_hours": 4,
                "series_name": "Weekly Farmers Market",
            },
            {
                "name": "Sunset Drum Circle at Karura",
                "description": "Free community drum circle every Sunday evening. Bring your own drum or percussion, or just come to dance and enjoy the vibe. We gather at the waterfall clearing as the sun sets. Magical energy.",
                "category": "concerts-and-nightlife",
                "venue": "Karura Forest",
                "location_tag": "nairobi",
                "lat": -1.2404,
                "lng": 36.8394,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 63,
                "event_type": "A",
                "start_offset_hours": -48,  # Past event
                "duration_hours": 3,
            },
            {
                "name": "Book Club: African Literature Discussion",
                "description": "Free monthly book club discussing contemporary African writers. This month: Chimamanda Ngozi Adichie's 'Americanah'. Coffee and snacks provided. All welcome, even if you haven't finished the book yet.",
                "category": "talks-and-ideas",
                "venue": "Alliance Française",
                "location_tag": "nairobi",
                "lat": -1.2644,
                "lng": 36.8078,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 28,
                "event_type": "A",
                "start_offset_hours": 336,  # Week 2
                "duration_hours": 2,
                "series_name": "Monthly Book Club",
            },
            {
                "name": "Community Clean-Up: Ngong Road Forest",
                "description": "Free volunteer event to clean up Ngong Road Forest trails. Gloves and trash bags provided. Bring water and sunscreen. We'll meet at the main gate and split into groups. Great way to give back while getting outdoors.",
                "category": "outdoors-and-active",
                "venue": "Ngong Road Forest",
                "location_tag": "nairobi",
                "lat": -1.3062,
                "lng": 36.7586,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 51,
                "event_type": "A",
                "start_offset_hours": -72,  # Past event
                "duration_hours": 3,
            },
            {
                "name": "Meditation & Mindfulness Workshop",
                "description": "Free introduction to meditation and breathwork. Suitable for complete beginners. Mats and cushions provided. Wear comfortable clothes. The studio is air-conditioned and peaceful — a true refuge from city noise.",
                "category": "workshops-and-classes",
                "venue": "Movement & Mindfulness Studio",
                "location_tag": "nairobi",
                "lat": -1.3218,
                "lng": 36.7073,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 34,
                "event_type": "A",
                "start_offset_hours": 504,  # Week 3
                "duration_hours": 2,
            },
            {
                "name": "Jazz Jam Session at Alchemist",
                "description": "Free entry weekly jazz jam. Bring your instrument and join in, or just enjoy the music. House band starts at 8pm, open jam from 9pm. The courtyard has the best sound on warm evenings.",
                "category": "concerts-and-nightlife",
                "venue": "Alchemist Bar",
                "location_tag": "nairobi",
                "lat": -1.2673,
                "lng": 36.8073,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 45,
                "event_type": "A",
                "start_offset_hours": -168,  # Past event
                "duration_hours": 4,
                "series_name": "Monday Jazz Sessions",
            },
            {
                "name": "Startup Founders Coffee Meetup",
                "description": "Free informal coffee meetup for startup founders and entrepreneurs. Share wins, challenges, and advice. No agenda, just connection. Meet at the upstairs seating area. First-timers always welcome.",
                "category": "talks-and-ideas",
                "venue": "Java House Westlands",
                "location_tag": "nairobi",
                "lat": -1.2650,
                "lng": 36.8100,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 22,
                "event_type": "A",
                "start_offset_hours": 672,  # Week 4
                "duration_hours": 2,
            },
            {
                "name": "Maasai Market at Village Market",
                "description": "Free entry weekly market featuring Maasai beadwork, fabrics, carvings, and crafts. Over 50 vendors. Haggling expected and encouraged. Proceeds support artisan cooperatives. Bring cash — most vendors don't take M-Pesa.",
                "category": "markets-and-popups",
                "venue": "Village Market",
                "location_tag": "nairobi",
                "lat": -1.2300,
                "lng": 36.8037,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 203,
                "event_type": "A",
                "start_offset_hours": -336,  # Past event
                "duration_hours": 6,
                "series_name": "Weekly Maasai Market",
            },
            {
                "name": "Photography Walk: Nairobi CBD",
                "description": "Free guided photo walk through downtown Nairobi. All cameras welcome (including phones). We'll cover street photography basics and explore hidden architectural gems. Meet at Jeevanjee Gardens at 9am.",
                "category": "culture-and-arts",
                "venue": "Jeevanjee Gardens",
                "location_tag": "nairobi",
                "lat": -1.2864,
                "lng": 36.8242,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 31,
                "event_type": "A",
                "start_offset_hours": 840,  # Week 5
                "duration_hours": 3,
            },
            {
                "name": "Women in Tech Networking Breakfast",
                "description": "Free networking breakfast for women in tech and STEM fields. Guest speaker, panel discussion, and breakout networking. Continental breakfast included. A supportive space to connect and grow.",
                "category": "talks-and-ideas",
                "venue": "Nairobi Garage",
                "location_tag": "nairobi",
                "lat": -1.2617,
                "lng": 36.7910,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 67,
                "event_type": "A",
                "start_offset_hours": -504,  # Past event
                "duration_hours": 3,
            },

            # TYPE B: Internal, Paid (with in-app ticketing) — 15 events
            {
                "name": "Blankets & Wine: Afrobeat Edition",
                "description": "Nairobi's iconic outdoor music festival returns with a stellar Afrobeat lineup. Expect performances from Sauti Sol, Nviiri the Storyteller, and surprise guest acts. Gates open at 2pm. Bring a blanket and sunscreen.",
                "category": "concerts-and-nightlife",
                "venue": "Ngong Racecourse",
                "location_tag": "nairobi",
                "lat": -1.3062,
                "lng": 36.7586,
                "price": Decimal("25"),
                "ticketing_enabled": True,
                "available_tickets": 450,
                "going_count": 387,
                "event_type": "B",
                "start_offset_hours": 96,  # This weekend
                "duration_hours": 8,
                "series_name": "Blankets & Wine",
            },
            {
                "name": "Rooftop Sunset Sessions: Live Band",
                "description": "Live music on our rooftop terrace with panoramic city views. This week featuring The Nairobi Horns Project. Full bar and kitchen available. Dress code: smart casual. Reserve early — this always sells out.",
                "category": "concerts-and-nightlife",
                "venue": "Rooftop Nairobi",
                "location_tag": "nairobi",
                "lat": -1.2650,
                "lng": 36.8100,
                "price": Decimal("15"),
                "ticketing_enabled": True,
                "available_tickets": 120,
                "going_count": 98,
                "event_type": "B",
                "start_offset_hours": 168,  # Next week
                "duration_hours": 5,
            },
            {
                "name": "Karura Forest Trail Run: 10K Challenge",
                "description": "Guided 10K trail run through Karura's scenic paths. All fitness levels welcome, water stations every 2km. T-shirt and finisher medal included. Entry fee covers forest conservation. Bring your own hydration pack.",
                "category": "outdoors-and-active",
                "venue": "Karura Forest",
                "location_tag": "nairobi",
                "lat": -1.2404,
                "lng": 36.8394,
                "price": Decimal("5"),
                "ticketing_enabled": True,
                "available_tickets": 150,
                "going_count": 89,
                "event_type": "B",
                "start_offset_hours": -96,  # Past event
                "duration_hours": 3,
            },
            {
                "name": "Street Food Festival: Nairobi Eats",
                "description": "Two-day celebration of Nairobi's street food scene. 40+ vendors serving mutura, bhajia, artisan burgers, and more. Live music, beer garden, kids' zone. Cash and M-Pesa accepted. Go early on Saturday — Sunday runs out of popular stalls by 3pm.",
                "category": "food-and-drink",
                "venue": "Ngong Racecourse",
                "location_tag": "nairobi",
                "lat": -1.3062,
                "lng": 36.7586,
                "price": Decimal("10"),
                "ticketing_enabled": True,
                "available_tickets": 800,
                "going_count": 564,
                "event_type": "B",
                "start_offset_hours": 240,  # Week 2
                "duration_hours": 48,
                "has_gallery": True,
                "gallery_description": "Photos from last year's festival showing the variety of food stalls, live music, and vibrant crowd.",
            },
            {
                "name": "Wine & Cheese Pairing Masterclass",
                "description": "Guided tasting of 6 wines paired with artisanal cheeses from Kenya and beyond. Expert sommelier walks you through flavor profiles. Limited to 20 guests for intimate experience. Book early — sells out within hours.",
                "category": "food-and-drink",
                "venue": "Alliance Française",
                "location_tag": "nairobi",
                "lat": -1.2644,
                "lng": 36.8078,
                "price": Decimal("35"),
                "ticketing_enabled": True,
                "available_tickets": 5,  # Almost sold out
                "going_count": 18,
                "event_type": "B",
                "start_offset_hours": -240,  # Past event
                "duration_hours": 3,
            },
            {
                "name": "Afro-Fusion Dance Workshop",
                "description": "3-hour intensive combining traditional African dance with contemporary and hip-hop styles. Beginner-friendly, no experience required. Wear comfortable athletic clothes and bring water. Studio gets warm — ceiling fans help but it's still a workout.",
                "category": "culture-and-arts",
                "venue": "GoDown Arts Centre",
                "location_tag": "nairobi",
                "lat": -1.2699,
                "lng": 36.8387,
                "price": Decimal("12"),
                "ticketing_enabled": True,
                "available_tickets": 25,
                "going_count": 18,
                "event_type": "B",
                "start_offset_hours": 336,  # Week 2
                "duration_hours": 3,
            },
            {
                "name": "Ceramics: Handbuilding Basics",
                "description": "Learn coil and slab techniques to create functional pottery. No experience needed. All materials and tools provided. Pieces will be fired and glazed — ready for pickup in 3 weeks. Wear clothes that can get dirty.",
                "category": "workshops-and-classes",
                "venue": "GoDown Arts Centre",
                "location_tag": "nairobi",
                "lat": -1.2699,
                "lng": 36.8387,
                "price": Decimal("28"),
                "ticketing_enabled": True,
                "available_tickets": 10,
                "going_count": 8,
                "event_type": "B",
                "start_offset_hours": -168,  # Past event
                "duration_hours": 4,
            },
            {
                "name": "Kiswahili for Beginners: 4-Week Course",
                "description": "Conversational Kiswahili course. One 2-hour session per week for 4 weeks. Focused on practical phrases and interactions. Small class size, interactive exercises. Workbook provided. Classes fill fast with expats — locals welcome too.",
                "category": "workshops-and-classes",
                "venue": "Alliance Française",
                "location_tag": "nairobi",
                "lat": -1.2644,
                "lng": 36.8078,
                "price": Decimal("40"),
                "ticketing_enabled": True,
                "available_tickets": 12,
                "going_count": 10,
                "event_type": "B",
                "start_offset_hours": 504,  # Week 3
                "duration_hours": 8,
            },
            {
                "name": "Nyege Nyege Nairobi: Electronic Music Night",
                "description": "East Africa's premier electronic music festival brings its Nairobi edition. Four stages, 30+ DJs, experimental beats from Kampala to Kinshasa. 18+ only, ID required. Upper deck at main stage is less crowded with better ventilation.",
                "category": "concerts-and-nightlife",
                "venue": "Ngong Racecourse",
                "location_tag": "nairobi",
                "lat": -1.3062,
                "lng": 36.7586,
                "price": Decimal("35"),
                "ticketing_enabled": True,
                "available_tickets": 280,
                "going_count": 412,
                "event_type": "B",
                "start_offset_hours": -336,  # Past event
                "duration_hours": 10,
            },
            {
                "name": "Nairobi Coffee Crawl",
                "description": "Guided walking tour visiting 5 of Nairobi's best specialty coffee roasters. Learn about Kenyan coffee production, cupping techniques, and brewing methods. Includes tastings at each stop. Wear comfortable shoes — 3km of walking.",
                "category": "food-and-drink",
                "venue": "Nairobi CBD",
                "location_tag": "nairobi",
                "lat": -1.2864,
                "lng": 36.8172,
                "price": Decimal("25"),
                "ticketing_enabled": True,
                "available_tickets": 15,
                "going_count": 12,
                "event_type": "B",
                "start_offset_hours": 672,  # Week 4
                "duration_hours": 3,
            },
            {
                "name": "Bread Making Workshop: Sourdough & Artisan Loaves",
                "description": "Full-day workshop learning to make sourdough starter and bake artisan bread. Hands-on throughout. Each participant bakes 2 loaves to take home. Lunch included. Held at a working bakery — you'll leave smelling like fresh bread.",
                "category": "workshops-and-classes",
                "venue": "Spring Valley Bakery",
                "location_tag": "nairobi",
                "lat": -1.2642,
                "lng": 36.7886,
                "price": Decimal("35"),
                "ticketing_enabled": True,
                "available_tickets": 8,
                "going_count": 7,
                "event_type": "B",
                "start_offset_hours": -504,  # Past event
                "duration_hours": 6,
            },
            {
                "name": "Vegan Brunch Pop-Up at Spring Valley",
                "description": "Plant-based brunch featuring innovative takes on Kenyan classics. Ugali made from purple sweet potato, coconut-based nyama choma substitute, passion fruit mimosas. Outdoor garden seating. Limited capacity, no walk-ins.",
                "category": "food-and-drink",
                "venue": "Spring Valley Community Market",
                "location_tag": "nairobi",
                "lat": -1.2642,
                "lng": 36.7886,
                "price": Decimal("18"),
                "ticketing_enabled": True,
                "available_tickets": 40,
                "going_count": 31,
                "event_type": "B",
                "start_offset_hours": 840,  # Week 5
                "duration_hours": 3,
            },
            {
                "name": "Digital Marketing for Small Business",
                "description": "Half-day intensive covering social media strategy, content creation, and analytics. Bring your laptop. Case studies from Kenyan businesses. Coffee and lunch included. Instructor worked at Safaricom for 10 years — practical over theory.",
                "category": "workshops-and-classes",
                "venue": "PAWA254",
                "location_tag": "nairobi",
                "lat": -1.3152,
                "lng": 36.8322,
                "price": Decimal("25"),
                "ticketing_enabled": True,
                "available_tickets": 25,
                "going_count": 19,
                "event_type": "B",
                "start_offset_hours": -672,  # Past event
                "duration_hours": 4,
            },
            {
                "name": "Poetry Slam: Spoken Word Showcase",
                "description": "Open mic poetry night with featured performers from Nairobi's slam poetry scene. Sign up to perform or just enjoy the show. Cash bar and light snacks. The basement venue at PAWA has incredible acoustics — no mic needed for the intimate crowd.",
                "category": "culture-and-arts",
                "venue": "PAWA254",
                "location_tag": "nairobi",
                "lat": -1.3152,
                "lng": 36.8322,
                "price": Decimal("5"),
                "ticketing_enabled": True,
                "available_tickets": 60,
                "going_count": 42,
                "event_type": "B",
                "start_offset_hours": 1008,  # Week 6
                "duration_hours": 3,
            },
            {
                "name": "Beading & Jewelry Making Class",
                "description": "Learn traditional Maasai beading techniques and create your own jewelry piece to take home. All materials provided. Taught by artisans from the Maasai Market collective. Small class size for personalized instruction. Bring reading glasses if needed — detailed work.",
                "category": "culture-and-arts",
                "venue": "The Hub Karen",
                "location_tag": "nairobi",
                "lat": -1.3218,
                "lng": 36.7073,
                "price": Decimal("25"),
                "ticketing_enabled": True,
                "available_tickets": 12,
                "going_count": 9,
                "event_type": "B",
                "start_offset_hours": -840,  # Past event
                "duration_hours": 3,
            },

            # TYPE C: External, Free — 10 events
            {
                "name": "Contemporary Kenyan Art Exhibition Opening",
                "description": "Month-long exhibition featuring 15 emerging Kenyan visual artists. Paintings, sculpture, mixed media exploring themes of identity, urbanization, and climate. Opening reception this Friday with artist talks. Free entry throughout the month.",
                "category": "culture-and-arts",
                "venue": "Circle Art Gallery",
                "location_tag": "nairobi",
                "lat": -1.2836,
                "lng": 36.7661,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 142,
                "event_type": "C",
                "start_offset_hours": 5,  # Tonight
                "duration_hours": 720,  # 30 days
                "more_details_url": "https://www.circleartgallery.com/exhibitions",
            },
            {
                "name": "Climate Action Panel Discussion",
                "description": "Environmental scientists, policymakers, and activists discuss climate adaptation strategies for Kenya. Moderated Q&A follows. Light refreshments served. Hosted by Nairobi National Museum. Free but RSVP required via museum website.",
                "category": "talks-and-ideas",
                "venue": "Nairobi National Museum",
                "location_tag": "nairobi",
                "lat": -1.2687,
                "lng": 36.8143,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 87,
                "event_type": "C",
                "start_offset_hours": -168,  # Past event
                "duration_hours": 2,
                "more_details_url": "https://www.museums.or.ke/events",
            },
            {
                "name": "Reggae Sundays at Carnivore",
                "description": "Open-air reggae session with DJ Fully Focus and live drum circle. Nyama choma and cocktails available for purchase. Free entry, pay-as-you-eat. Bring cash — M-Pesa at the bar has been unreliable lately. Family-friendly atmosphere.",
                "category": "concerts-and-nightlife",
                "venue": "Carnivore Restaurant",
                "location_tag": "nairobi",
                "lat": -1.3297,
                "lng": 36.8092,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 134,
                "event_type": "C",
                "start_offset_hours": 96,  # This weekend
                "duration_hours": 6,
                "series_name": "Reggae Sundays",
                "more_details_url": "https://tamarind.co.ke/carnivore/events",
            },
            {
                "name": "Tech Startup Pitch Night",
                "description": "Watch 8 Kenyan startups pitch their ideas to a panel of investors. Followed by networking session with founders, VCs, and the tech community. Free entry, drink minimum KES 500. Bring business cards — networking after is where the real deals happen.",
                "category": "talks-and-ideas",
                "venue": "PAWA254",
                "location_tag": "nairobi",
                "lat": -1.3152,
                "lng": 36.8322,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 98,
                "event_type": "C",
                "start_offset_hours": 240,  # Week 2
                "duration_hours": 3,
                "more_details_url": "https://pawa254.org/events",
            },
            {
                "name": "Vintage Fashion & Vinyl Records Popup",
                "description": "Curated vintage clothing and record sale. 10 vendors with 60s-90s fashion and rare East African vinyl. Try-on mirrors available. Cash and M-Pesa. DJ spinning records all day. Upstairs section has the best clothing picks — less picked over.",
                "category": "markets-and-popups",
                "venue": "Alchemist Bar",
                "location_tag": "nairobi",
                "lat": -1.2673,
                "lng": 36.8073,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 87,
                "event_type": "C",
                "start_offset_hours": -336,  # Past event
                "duration_hours": 6,
                "more_details_url": "https://alchemistbar.co.ke/events",
            },
            {
                "name": "Nairobi Film Festival Free Screening",
                "description": "Free outdoor screening of award-winning Kenyan documentary. Part of Nairobi Film Festival week. Bring a mat or chair. Popcorn and drinks for sale. Q&A with filmmakers after the screening. Gates open at 6pm, film starts at 7pm.",
                "category": "culture-and-arts",
                "venue": "Alliance Française Courtyard",
                "location_tag": "nairobi",
                "lat": -1.2644,
                "lng": 36.8078,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 156,
                "event_type": "C",
                "start_offset_hours": 336,  # Week 2
                "duration_hours": 3,
                "more_details_url": "https://www.alliance-francaise.or.ke/film-festival",
            },
            {
                "name": "Outdoor Yoga & Meditation at Arboretum",
                "description": "Free morning yoga and meditation session in the serene Nairobi Arboretum. All levels welcome. Bring your own mat. Guided by certified instructor. Optional coffee and light snacks available for purchase after class. Arrive 10 min early for best shaded spot.",
                "category": "outdoors-and-active",
                "venue": "Nairobi Arboretum",
                "location_tag": "nairobi",
                "lat": -1.2820,
                "lng": 36.8084,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 64,
                "event_type": "C",
                "start_offset_hours": -504,  # Past event
                "duration_hours": 2,
                "more_details_url": "https://nairobiforestconservancy.org/events",
            },
            {
                "name": "Sunday Brunch Live Music at Brew Bistro",
                "description": "Free live acoustic music every Sunday during brunch service. Full brunch menu available for purchase. Reservations recommended for tables. Walk-ins welcome at the bar. Music starts at noon. Great vibes, good food, no cover charge.",
                "category": "food-and-drink",
                "venue": "Brew Bistro Westlands",
                "location_tag": "nairobi",
                "lat": -1.2650,
                "lng": 36.8100,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 89,
                "event_type": "C",
                "start_offset_hours": 504,  # Week 3
                "duration_hours": 4,
                "series_name": "Sunday Brunch Sessions",
                "more_details_url": "https://brewbistro.co.ke/events",
            },
            {
                "name": "Nairobi Design Week Open Studios",
                "description": "Free access to local designers' studios during Nairobi Design Week. Meet fashion designers, graphic artists, and product designers. See works in progress and finished pieces. Self-guided studio tour across Kilimani and Lavington. Map provided.",
                "category": "culture-and-arts",
                "venue": "Multiple Studios",
                "location_tag": "nairobi",
                "lat": -1.2820,
                "lng": 36.7750,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 73,
                "event_type": "C",
                "start_offset_hours": -672,  # Past event
                "duration_hours": 8,
                "more_details_url": "https://nairobidesignweek.com",
            },
            {
                "name": "Community Garden Workshop",
                "description": "Free hands-on workshop on urban farming and container gardening. Learn to grow vegetables in small spaces. Seedlings and planting tips provided. Hosted by Nairobi City County Urban Agriculture Program. Register online to confirm attendance.",
                "category": "workshops-and-classes",
                "venue": "City Park",
                "location_tag": "nairobi",
                "lat": -1.2657,
                "lng": 36.8297,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 42,
                "event_type": "C",
                "start_offset_hours": 672,  # Week 4
                "duration_hours": 3,
                "more_details_url": "https://www.nairobi.go.ke/agriculture/events",
            },

            # TYPE D: External, Paid — 10 events
            {
                "name": "Nairobi International Film Festival",
                "description": "Week-long showcase of African and international cinema. 40+ films across documentary, feature, and short categories. This year's focus: climate stories from the Global South. Opening night gala includes Q&A with filmmakers. Book tickets via festival website.",
                "category": "culture-and-arts",
                "venue": "Alliance Française",
                "location_tag": "nairobi",
                "lat": -1.2644,
                "lng": 36.8078,
                "price": Decimal("8"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 178,
                "event_type": "D",
                "start_offset_hours": 336,  # Week 2
                "duration_hours": 168,  # 7 days
                "more_details_url": "https://www.alliance-francaise.or.ke/film-festival/tickets",
                "has_gallery": True,
                "gallery_description": "Film stills from this year's featured selections and behind-the-scenes photos from the festival setup.",
            },
            {
                "name": "TEDx Nairobi: Ideas Worth Spreading",
                "description": "Full-day conference featuring 12 speakers on innovation, culture, and social change. Networking breaks, lunch, and evening reception included. Past speakers include Lupita Nyong'o and Juliani. Early bird pricing ends 2 weeks before event. Tickets via TEDx website.",
                "category": "talks-and-ideas",
                "venue": "Sarit Centre",
                "location_tag": "nairobi",
                "lat": -1.2617,
                "lng": 36.7910,
                "price": Decimal("50"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 245,
                "event_type": "D",
                "start_offset_hours": 840,  # Week 5
                "duration_hours": 8,
                "more_details_url": "https://tedxnairobi.com/tickets",
            },
            {
                "name": "Kiswahili Theatre: Machozi ya Maendeleo",
                "description": "Original play performed in Kiswahili exploring gentrification and displacement in Nairobi's eastlands. Powerful ensemble cast. English subtitles projected. Two-act play with intermission. Tickets available at Kenya National Theatre box office or online.",
                "category": "culture-and-arts",
                "venue": "Kenya National Theatre",
                "location_tag": "nairobi",
                "lat": -1.2781,
                "lng": 36.8210,
                "price": Decimal("10"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 89,
                "event_type": "D",
                "start_offset_hours": -240,  # Past event
                "duration_hours": 3,
                "more_details_url": "https://kenyatheatre.or.ke/bookings",
            },
            {
                "name": "Nairobi Restaurant Week",
                "description": "Two-week dining festival featuring prix-fixe menus at 50+ Nairobi restaurants. 2-course lunch menus and 3-course dinner menus at special pricing. Reservations required — book directly with restaurants. Full participating list on festival website.",
                "category": "food-and-drink",
                "venue": "Various Restaurants",
                "location_tag": "nairobi",
                "lat": -1.2821,
                "lng": 36.8219,
                "price": Decimal("20"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 312,
                "event_type": "D",
                "start_offset_hours": 168,  # Next week
                "duration_hours": 336,  # 14 days
                "more_details_url": "https://nairobirestaurantweek.com",
            },
            {
                "name": "Jazz Fusion Concert: Nairobi Horns Project",
                "description": "The legendary Nairobi Horns Project performs an evening of Afro-jazz fusion. Expect improvisation, call-and-response, and infectious rhythms. Seated venue, limited standing room. Cash bar, no food service. Rare Nairobi appearance — tickets via Ticketsasa.",
                "category": "concerts-and-nightlife",
                "venue": "Alliance Française",
                "location_tag": "nairobi",
                "lat": -1.2644,
                "lng": 36.8078,
                "price": Decimal("15"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 71,
                "event_type": "D",
                "start_offset_hours": -336,  # Past event
                "duration_hours": 3,
                "more_details_url": "https://www.ticketsasa.com/events",
            },
            {
                "name": "Lamu Cultural Heritage Weekend",
                "description": "3-day guided tour of Lamu Old Town — UNESCO World Heritage Site. Includes dhow sailing, Swahili cooking class, spice market visit, and historical walking tour. Accommodation and most meals included. Book flights separately. Tickets via tour operator website.",
                "category": "travel",
                "venue": "Lamu Old Town",
                "location_tag": "mombasa",
                "lat": -2.2717,
                "lng": 40.9020,
                "price": Decimal("50"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 9,
                "event_type": "D",
                "start_offset_hours": 672,  # Week 4
                "duration_hours": 72,
                "more_details_url": "https://lamuheritage.tours/book",
            },
            {
                "name": "Craft Beer Tasting: East African Breweries",
                "description": "Sample 8 craft beers from Kenya, Tanzania, and Uganda. Meet the brewers, learn the stories behind each brew. Light bites included. Held at Brew Bistro's outdoor terrace. Generous pours. Purchase tickets online or at the door (subject to availability).",
                "category": "food-and-drink",
                "venue": "Brew Bistro",
                "location_tag": "nairobi",
                "lat": -1.2650,
                "lng": 36.8100,
                "price": Decimal("20"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 28,
                "event_type": "D",
                "start_offset_hours": 504,  # Week 3
                "duration_hours": 3,
                "more_details_url": "https://brewbistro.co.ke/tastings",
            },
            {
                "name": "Photography Workshop: Street Photography Nairobi",
                "description": "Half-day workshop covering street photography techniques. Morning classroom session followed by guided walk through Nairobi streets. Bring your camera (phone cameras welcome). Lunch included. Instructor is a Magnum photographer. Book via workshop website.",
                "category": "talks-and-ideas",
                "venue": "GoDown Arts Centre",
                "location_tag": "nairobi",
                "lat": -1.2699,
                "lng": 36.8387,
                "price": Decimal("35"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 12,
                "event_type": "D",
                "start_offset_hours": -504,  # Past event
                "duration_hours": 5,
                "more_details_url": "https://nairobiworkshops.com/photography",
            },
            {
                "name": "Holiday Gift Bazaar",
                "description": "Two-day shopping event with 60+ local artisans and makers. Jewelry, home decor, skincare, gourmet foods, children's items. Gift wrapping available. Live entertainment. KES 200 entry supports participating artisans. Tickets at the door or online.",
                "category": "markets-and-popups",
                "venue": "The Hub Karen",
                "location_tag": "nairobi",
                "lat": -1.3218,
                "lng": 36.7073,
                "price": Decimal("2"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 342,
                "event_type": "D",
                "start_offset_hours": -840,  # Past event
                "duration_hours": 16,
                "more_details_url": "https://thehubkaren.com/bazaar",
            },
            {
                "name": "Mt. Kenya Climbing Expedition: Sirimon Route",
                "description": "5-day trek to Point Lenana (4,985m), Mt. Kenya's third-highest peak. All camping gear, porters, and meals included. Experienced mountain guide. Moderate to challenging fitness required. Acclimatization built in. Book via adventure tour operator.",
                "category": "travel",
                "venue": "Mt. Kenya National Park",
                "location_tag": "nairobi",
                "lat": -0.1521,
                "lng": 37.3084,
                "price": Decimal("42"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 5,
                "event_type": "D",
                "start_offset_hours": 1176,  # Week 7
                "duration_hours": 120,
                "more_details_url": "https://mtkenya.adventures/sirimon-route",
            },
        ]

        events = []
        for data in events_data:
            category = categories[data["category"]]

            # Calculate start date
            start_date = now + timedelta(hours=data["start_offset_hours"])
            end_date = start_date + timedelta(hours=data["duration_hours"])

            # Fetch image
            image_url = fetch_unsplash_image_url(data["category"])

            # Fetch gallery images if needed
            gallery_images = []
            gallery_description = None
            if data.get("has_gallery"):
                gallery_images = fetch_unsplash_gallery_images(data["category"], 3)
                gallery_description = data.get("gallery_description")

            # Determine organizer based on event type
            # All events (A, B, C, D) are attributed to internal organizers
            # External events (C, D) have more_details_url but still have an organizer
            organizer_index = hash(data["name"]) % len(organizers)
            organizer = organizers[organizer_index]

            # Determine event status based on timing
            if data["start_offset_hours"] < 0:
                # Past event
                status = "ended"
            else:
                # Upcoming event
                status = "live"

            # Create event
            event, created = Event.objects.update_or_create(
                name=data["name"],
                defaults={
                    "organizer": organizer,
                    "description": data["description"],
                    "date": start_date,
                    "end_date": end_date,
                    "image": image_url,
                    "timezone": "Africa/Nairobi",
                    "location_name": data["venue"],
                    "location": Point(data["lng"], data["lat"], srid=4326),
                    "price": data["price"],
                    "ticketing_enabled": data["ticketing_enabled"],
                    "available_tickets": data.get("available_tickets"),
                    "going_count": data["going_count"],
                    "series_name": data.get("series_name"),
                    "more_details_url": data.get("more_details_url"),
                    "has_gallery": data.get("has_gallery", False),
                    "gallery_images": gallery_images,
                    "gallery_description": gallery_description,
                    "is_active": True,
                    "status": status,
                }
            )
            event.category.set([category])
            events.append(event)

        return events

    def _seed_ticket_tiers(self, events):
        """Create 2 ticket tiers for each Type B (internal paid) event"""
        tiers_count = 0

        for event in events:
            # Only add tiers for paid internal events (ticketing_enabled=True)
            if not event.ticketing_enabled:
                continue

            # Early Bird tier
            tier1, _ = TicketTier.objects.get_or_create(
                event=event,
                name="Early Bird",
                defaults={
                    "description": "Limited early bird discount",
                    "price": max(Decimal("1"), event.price * Decimal("0.8")),  # 20% off
                    "capacity": 50,
                    "available": 50,
                    "is_active": True,
                    "sort_order": 1,
                }
            )
            tiers_count += 1

            # General Admission tier
            tier2, _ = TicketTier.objects.get_or_create(
                event=event,
                name="General Admission",
                defaults={
                    "description": "Standard entry ticket",
                    "price": event.price,
                    "capacity": 100,
                    "available": 100,
                    "is_active": True,
                    "sort_order": 2,
                }
            )
            tiers_count += 1

        return tiers_count

    def _seed_user_interactions(self, events):
        """
        Create diverse user interactions for varied recommendations.
        Going RSVPs only for Type A (free internal) and external events (Types C and D).
        NO going RSVPs for Type B (paid internal with ticketing).
        """
        users = list(User.objects.all())

        if not users:
            self.stdout.write(self.style.WARNING("No users found — skipping interaction seeding"))
            return 0

        # Find faithcathy12@gmail.com
        faith_user = next((u for u in users if u.email == "faithcathy12@gmail.com"), None)
        other_users = [u for u in users if u.email != "faithcathy12@gmail.com"]

        import random
        random.seed(42)

        interaction_count = 0

        # Create name to slug mapping
        name_to_slug = {
            "Concerts & Nightlife": "concerts-and-nightlife",
            "Outdoors & Active": "outdoors-and-active",
            "Food & Drink": "food-and-drink",
            "Culture & Arts": "culture-and-arts",
            "Talks & Ideas": "talks-and-ideas",
            "Workshops & Classes": "workshops-and-classes",
            "Markets & Popups": "markets-and-popups",
            "Travel": "travel",
        }

        # Separate past and upcoming events
        past_events = [e for e in events if e.status == "ended"]
        upcoming_events = [e for e in events if e.status == "live"]

        # Faith gets the most interactions
        if faith_user:
            # Past events: 8-10 interactions (mix of saved and going)
            faith_past_sample = random.sample(past_events, min(10, len(past_events)))
            for event in faith_past_sample:
                # Save the event
                UserEvents.objects.get_or_create(user=faith_user, event=event)
                interaction_count += 1

                # Going only for Type A and external events (not Type B paid ticketed)
                if not event.ticketing_enabled or event.more_details_url:
                    EventGoing.objects.get_or_create(user=faith_user, event=event)
                    interaction_count += 1

            # Upcoming events: 3-5 interactions (mix of saved and going)
            faith_upcoming_sample = random.sample(upcoming_events, min(5, len(upcoming_events)))
            for event in faith_upcoming_sample:
                # Save the event
                UserEvents.objects.get_or_create(user=faith_user, event=event)
                interaction_count += 1

                # Going only for Type A and external events
                if not event.ticketing_enabled or event.more_details_url:
                    EventGoing.objects.get_or_create(user=faith_user, event=event)
                    interaction_count += 1

        # Other users get varied interactions
        for user in other_users:
            # Random interest pattern
            interest_categories = random.sample(
                list(name_to_slug.values()),
                k=random.randint(2, 4),
            )

            # Filter events by user's interests
            interested_events = [
                e
                for e in events
                if e.category.first() and name_to_slug.get(e.category.first().name) in interest_categories
            ]

            # Save 2-5 random events from their interest categories
            events_to_interact = random.sample(interested_events, min(random.randint(2, 5), len(interested_events)))

            for event in events_to_interact:
                # Always save
                UserEvents.objects.get_or_create(user=user, event=event)
                interaction_count += 1

                # Going only for Type A and external events (50% chance)
                if (not event.ticketing_enabled or event.more_details_url) and random.random() < 0.5:
                    EventGoing.objects.get_or_create(user=user, event=event)
                    interaction_count += 1

        return interaction_count

    def _seed_editors_picks(self, events):
        """Create editor's picks for different locations and time periods"""
        now = timezone.now()

        # Select strong events with good descriptions for editor's picks
        upcoming_events = [e for e in events if e.status == "live"]
        concerts_events = [e for e in upcoming_events if e.category.first() and e.category.first().name == "Concerts & Nightlife"]
        culture_events = [e for e in upcoming_events if e.category.first() and e.category.first().name == "Culture & Arts"]
        food_events = [e for e in upcoming_events if e.category.first() and e.category.first().name == "Food & Drink"]

        picks_data = [
            {
                "event": concerts_events[0] if concerts_events else upcoming_events[0],
                "location_tag": "nairobi",
                "active_from": now,
                "active_until": now + timedelta(days=7),
                "curator_note": "Nairobi's most iconic outdoor music festival. The vibe is unmatched — arrive early for the best lawn spots and pack sunscreen.",
                "curator_name": "Kamau, Pursuit",
                "position": 1,
            },
            {
                "event": culture_events[0] if culture_events else upcoming_events[1],
                "location_tag": "nairobi",
                "active_from": now + timedelta(days=7),
                "active_until": now + timedelta(days=14),
                "curator_note": "A must-see exhibition showcasing Kenya's emerging art scene. The opening reception is always electric with great conversation.",
                "curator_name": "Pursuit team",
                "position": 1,
            },
            {
                "event": food_events[0] if food_events else upcoming_events[2],
                "location_tag": "mombasa",
                "active_from": now,
                "active_until": now + timedelta(days=7),
                "curator_note": "The coast's best street food comes together in one place. Go hungry and pace yourself — there's a lot to taste.",
                "curator_name": "Pursuit team",
                "position": 1,
            },
        ]

        picks_count = 0
        for pick_data in picks_data:
            if pick_data["event"]:
                EditorsPick.objects.update_or_create(
                    event=pick_data["event"],
                    location_tag=pick_data["location_tag"],
                    active_from=pick_data["active_from"],
                    defaults={
                        "active_until": pick_data["active_until"],
                        "curator_note": pick_data["curator_note"],
                        "curator_name": pick_data["curator_name"],
                        "position": pick_data["position"],
                    },
                )
                picks_count += 1

        return picks_count

    # Trips feature temporarily removed — seed commented out
    # TODO: re-enable when trips feature is restored
    #
    # def _seed_trips(self, events):
    #     """Create trips for some users with associated events"""
    #     users = list(User.objects.all())
    #
    #     if not users:
    #         return 0
    #
    #     import random
    #     random.seed(42)
    #
    #     now = timezone.now()
    #     # Get travel events for trips
    #     travel_events = [e for e in events if e.category.first() and e.category.first().name == "Travel"]
    #
    #     trips_data = [
    #         {
    #             "name": "Coastal Getaway: Lamu & Diani",
    #             "destination": "Lamu & Diani Beach",
    #             "start_date": now + timedelta(days=21),
    #             "end_date": now + timedelta(days=28),
    #             "image": "https://images.unsplash.com/photo-1559827260-dc66d52bef19",
    #         },
    #         {
    #             "name": "Mt. Kenya Adventure",
    #             "destination": "Mt. Kenya & Nanyuki",
    #             "start_date": now + timedelta(days=28),
    #             "end_date": now + timedelta(days=33),
    #             "image": "https://images.unsplash.com/photo-1589553416260-f586c8f1514f",
    #         },
    #     ]
    #
    #     trips_count = 0
    #
    #     # Assign trips to different users
    #     for idx, trip_data in enumerate(trips_data):
    #         if idx >= len(users):
    #             break
    #
    #         user = users[idx]
    #
    #         trip, created = Trip.objects.update_or_create(
    #             user=user,
    #             name=trip_data["name"],
    #             defaults={
    #                 "destination": trip_data["destination"],
    #                 "start_date": trip_data["start_date"],
    #                 "end_date": trip_data["end_date"],
    #                 "image": trip_data["image"],
    #             }
    #         )
    #
    #         # Add 1-2 travel events to each trip
    #         trip_events = random.sample(travel_events, min(2, len(travel_events)))
    #         for event in trip_events:
    #             trip.events.add(event)
    #
    #         trips_count += 1
    #
    #     return trips_count
