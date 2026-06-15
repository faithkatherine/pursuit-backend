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
from apps.events.models import EditorsPick, Event, UserEvents
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
            # Flush event-related data
            UserEvents.objects.all().delete()
            EditorsPick.objects.all().delete()
            Event.objects.all().delete()
            Trip.objects.all().delete()
            Category.objects.all().delete()

            self.stdout.write(self.style.SUCCESS("✓ Flushed all event data\n"))

            # Seed organizer
            self.stdout.write("👤 Creating organizer...")
            organizer = self._seed_organizer()
            self.stdout.write(self.style.SUCCESS(f"✓ Created organizer: {organizer.business_name}\n"))

            # Seed categories
            self.stdout.write("📂 Creating categories...")
            categories = self._seed_categories()
            self.stdout.write(self.style.SUCCESS(f"✓ Created {len(categories)} categories\n"))

            # Seed events
            self.stdout.write("🎉 Creating events...")
            events = self._seed_events(categories, organizer)
            self.stdout.write(self.style.SUCCESS(f"✓ Created {len(events)} events\n"))

            # Seed user interactions
            self.stdout.write("❤️  Creating user interactions...")
            interaction_count = self._seed_user_interactions(events)
            self.stdout.write(self.style.SUCCESS(f"✓ Created {interaction_count} user interactions\n"))

            # Seed editor's picks
            self.stdout.write("⭐ Creating editor's picks...")
            picks_count = self._seed_editors_picks(events)
            self.stdout.write(self.style.SUCCESS(f"✓ Created {picks_count} editor's picks\n"))

            # Seed trips
            self.stdout.write("✈️  Creating trips...")
            trips_count = self._seed_trips(events)
            self.stdout.write(self.style.SUCCESS(f"✓ Created {trips_count} trips\n"))

            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✅ Seed complete: {len(events)} events, {interaction_count} interactions, {picks_count} picks, {trips_count} trips\n"
                )
            )

    def _seed_organizer(self):
        """Create a default organizer for seeded events"""
        # Get or create a default organizer user
        user, _ = User.objects.get_or_create(
            email="organizer@pursuitapp.co.ke",
            defaults={
                "first_name": "Pursuit",
                "last_name": "Events",
                "is_active": True,
            }
        )

        # Create organizer profile
        organizer, _ = OrganizerProfile.objects.get_or_create(
            user=user,
            defaults={
                "business_name": "Pursuit Events HQ",
                "verified": True,
            }
        )

        return organizer

    def _seed_categories(self):
        """Create the 8 core categories"""
        # Map slug to category data for easier lookup
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

    def _seed_events(self, categories, organizer):
        """Create 50 diverse events across all categories and time ranges"""
        nairobi_tz = ZoneInfo("Africa/Nairobi")
        now = timezone.now().astimezone(nairobi_tz)

        events_data = [
            # CONCERTS & NIGHTLIFE (8 events)
            {
                "name": "Blankets & Wine: Afrobeat Edition",
                "description": "Nairobi's iconic outdoor music festival returns with a stellar Afrobeat lineup. Expect performances from Sauti Sol, Nviiri the Storyteller, and surprise guest acts. Gates open at 2pm — bring a blanket and sunscreen. Pro tip: the left side of the stage near the food trucks has the best sound and shade by 5pm.",
                "category": "concerts-and-nightlife",
                "venue": "Ngong Racecourse",
                "neighbourhood": "Ngong Road",
                "location_tag": "nairobi",
                "lat": -1.3062,
                "lng": 36.7586,
                "price": Decimal("2500"),
                "ticketing_enabled": True,
                "available_tickets": 450,
                "going_count": 387,
                "series_name": "Blankets & Wine",
                "start_offset_hours": 72,  # This weekend
                "duration_hours": 8,
            },
            {
                "name": "Jazz Mondays at Alchemist",
                "description": "Intimate live jazz session with rotating local and regional acts. This week features the Nairobi Horns Project. Full bar and kitchen available. No cover charge, but arrive by 8pm to secure courtyard seating — indoor gets packed and the sound isn't as crisp.",
                "category": "concerts-and-nightlife",
                "venue": "Alchemist Bar",
                "neighbourhood": "Westlands",
                "location_tag": "nairobi",
                "lat": -1.2673,
                "lng": 36.8073,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 67,
                "series_name": "Jazz Mondays",
                "start_offset_hours": 4,  # Tonight
                "duration_hours": 4,
                "more_details_url": "https://alchemistbar.co.ke/events",
            },
            {
                "name": "Nyege Nyege Nairobi: Electronic Music Showcase",
                "description": "East Africa's premier electronic music festival brings its Nairobi edition. Four stages, 30+ DJs, experimental beats from Kampala to Kinshasa. 18+ only, ID required at the door. The upper deck at the main stage is less crowded and has better ventilation.",
                "category": "concerts-and-nightlife",
                "venue": "Ngong Racecourse",
                "neighbourhood": "Ngong Road",
                "location_tag": "nairobi",
                "lat": -1.3062,
                "lng": 36.7586,
                "price": Decimal("3500"),
                "ticketing_enabled": True,
                "available_tickets": 280,
                "going_count": 412,
                "start_offset_hours": 168,  # Next week
                "duration_hours": 10,
            },
            {
                "name": "Rhumba Night: Congolese Classics",
                "description": "Live Congolese rhumba band performing hits from Koffi Olomide, Fally Ipupa, and Madilu System. Full dinner service available. Smart casual dress code. Get there before 9pm — the dance floor fills fast and parking becomes a nightmare.",
                "category": "concerts-and-nightlife",
                "venue": "Alchemist Bar",
                "neighbourhood": "Westlands",
                "location_tag": "nairobi",
                "lat": -1.2673,
                "lng": 36.8073,
                "price": Decimal("1500"),
                "ticketing_enabled": True,
                "available_tickets": 120,
                "going_count": 89,
                "start_offset_hours": 336,  # Week 2
                "duration_hours": 5,
            },
            {
                "name": "Reggae Sundays at Carnivore",
                "description": "Open-air reggae session with DJ Fully Focus and live drum circle. Nyama choma and cocktails available. Free entry, pay-as-you-eat. Bring cash — M-Pesa at the bar has been unreliable lately.",
                "category": "concerts-and-nightlife",
                "venue": "Carnivore Restaurant",
                "neighbourhood": "Langata",
                "location_tag": "nairobi",
                "lat": -1.3297,
                "lng": 36.8092,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 134,
                "series_name": "Reggae Sundays",
                "start_offset_hours": 96,  # This weekend
                "duration_hours": 6,
                "more_details_url": "https://tamarind.co.ke/carnivore",
            },
            {
                "name": "Amapiano Block Party: South African Invasion",
                "description": "All-night amapiano session with DJs from Johannesburg and Lagos. Two floors, outdoor smoking lounge, full bar. 18+ strictly enforced. The rooftop section opens at 11pm and has better air circulation — worth the wait.",
                "category": "concerts-and-nightlife",
                "venue": "PAWA254",
                "neighbourhood": "Nairobi West",
                "location_tag": "nairobi",
                "lat": -1.3152,
                "lng": 36.8322,
                "price": Decimal("800"),
                "ticketing_enabled": True,
                "available_tickets": 200,
                "going_count": 156,
                "start_offset_hours": 504,  # Week 3
                "duration_hours": 8,
            },
            {
                "name": "Taarab Night: Coastal Music in the City",
                "description": "Traditional Swahili taarab music performed by Mombasa's Zuhura Swaleh and her ensemble. Intimate seated venue, limited capacity. Snacks and coastal-inspired cocktails. This is a rare Nairobi appearance — book early.",
                "category": "concerts-and-nightlife",
                "venue": "GoDown Arts Centre",
                "neighbourhood": "Ngara",
                "location_tag": "nairobi",
                "lat": -1.2699,
                "lng": 36.8387,
                "price": Decimal("1200"),
                "ticketing_enabled": True,
                "available_tickets": 0,  # SOLD OUT
                "going_count": 95,
                "start_offset_hours": 240,  # Week 2
                "duration_hours": 3,
            },
            {
                "name": "Open Mic Comedy & Music Jam",
                "description": "Weekly open mic for comedians, poets, and musicians. Sign-up starts at 7pm, show at 8pm. Free entry, drink minimum KES 500. Snacks available. The back corner tables have the best view without being too close to hecklers.",
                "category": "concerts-and-nightlife",
                "venue": "Alchemist Bar",
                "neighbourhood": "Westlands",
                "location_tag": "nairobi",
                "lat": -1.2673,
                "lng": 36.8073,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 43,
                "series_name": "Open Mic Tuesdays",
                "start_offset_hours": 672,  # Week 4
                "duration_hours": 4,
                "more_details_url": "https://alchemistbar.co.ke/events",
            },
            # OUTDOORS & ACTIVE (7 events)
            {
                "name": "Karura Forest Morning Run: 10K Trail",
                "description": "Guided group run through Karura's scenic trails. All fitness levels welcome, water stations every 2km. Meet at the main gate. Bring your own water bottle — the forest taps run slow in dry season. Entry fee covers forest conservation.",
                "category": "outdoors-and-active",
                "venue": "Karura Forest",
                "neighbourhood": "Gigiri",
                "location_tag": "nairobi",
                "lat": -1.2404,
                "lng": 36.8394,
                "price": Decimal("300"),
                "ticketing_enabled": True,
                "available_tickets": 150,
                "going_count": 78,
                "series_name": "Karura Runners",
                "start_offset_hours": 15,  # Tomorrow morning
                "duration_hours": 2,
            },
            {
                "name": "Ngong Hills Sunrise Hike",
                "description": "Challenging 3-hour hike to catch sunrise over the Rift Valley. Depart Nairobi at 5am, return by 11am. Moderate fitness required. Bring layered clothing and sturdy shoes — it's windy and muddy at the top even in dry season.",
                "category": "outdoors-and-active",
                "venue": "Ngong Hills",
                "neighbourhood": "Ngong",
                "location_tag": "nairobi",
                "lat": -1.3917,
                "lng": 36.6516,
                "price": Decimal("1500"),
                "ticketing_enabled": True,
                "available_tickets": 45,
                "going_count": 38,
                "start_offset_hours": 72,  # This weekend
                "duration_hours": 6,
            },
            {
                "name": "Cycle the City: Nairobi Bike Tour",
                "description": "Guided 15km bike tour through Nairobi's neighborhoods — from Uhuru Park to Kibera viewpoint to CBD. Bikes and helmets provided. Moderate pace with photo stops. Traffic is lighter on Sundays, but bring sunscreen regardless.",
                "category": "outdoors-and-active",
                "venue": "Uhuru Park",
                "neighbourhood": "CBD",
                "location_tag": "nairobi",
                "lat": -1.2833,
                "lng": 36.8172,
                "price": Decimal("2000"),
                "ticketing_enabled": True,
                "available_tickets": 25,
                "going_count": 19,
                "start_offset_hours": 96,  # This weekend
                "duration_hours": 3,
            },
            {
                "name": "Rock Climbing at Hell's Gate",
                "description": "Day trip to Hell's Gate National Park for rock climbing and gorge exploration. Transport from Nairobi included. All equipment provided, beginner-friendly. Bring packed lunch and 2L water minimum — the park has limited food options and it gets hot.",
                "category": "outdoors-and-active",
                "venue": "Hell's Gate National Park",
                "neighbourhood": "Naivasha",
                "location_tag": "naivasha",
                "lat": -0.9186,
                "lng": 36.3111,
                "price": Decimal("4500"),
                "ticketing_enabled": True,
                "available_tickets": 20,
                "going_count": 16,
                "start_offset_hours": 168,  # Next week
                "duration_hours": 10,
            },
            {
                "name": "Parkrun Nairobi: 5K Saturday Run",
                "description": "Free weekly 5K run at Karura Forest. Timed run, all abilities welcome. Register online before your first run. Kids' 2K starts at 8am. Bring barcode — registration desk closes at 9am sharp.",
                "category": "outdoors-and-active",
                "venue": "Karura Forest",
                "neighbourhood": "Gigiri",
                "location_tag": "nairobi",
                "lat": -1.2404,
                "lng": 36.8394,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 210,
                "series_name": "Parkrun Nairobi",
                "start_offset_hours": 72,  # This weekend
                "duration_hours": 1,
                "more_details_url": "https://www.parkrun.com/nairobi/",
            },
            {
                "name": "Mt. Longonot Crater Hike",
                "description": "Challenging full-day hike up Mt. Longonot with crater rim walk. Stunning Rift Valley views. Transport from Nairobi included, park fees covered. Start early — the final ascent is steep and exposed to sun. Bring 3L water per person.",
                "category": "outdoors-and-active",
                "venue": "Mt. Longonot National Park",
                "neighbourhood": "Naivasha",
                "location_tag": "naivasha",
                "lat": -0.9148,
                "lng": 36.4461,
                "price": Decimal("3000"),
                "ticketing_enabled": True,
                "available_tickets": 35,
                "going_count": 27,
                "start_offset_hours": 336,  # Week 2
                "duration_hours": 8,
            },
            {
                "name": "Outdoor Yoga at Arboretum",
                "description": "Morning vinyasa flow class in the serene Nairobi Arboretum. All levels, mats provided. Followed by optional brunch at the on-site café. Arrive 10 minutes early to secure a shaded spot — the sun gets intense by 10am.",
                "category": "outdoors-and-active",
                "venue": "Nairobi Arboretum",
                "neighbourhood": "Kilimani",
                "location_tag": "nairobi",
                "lat": -1.2820,
                "lng": 36.8084,
                "price": Decimal("800"),
                "ticketing_enabled": True,
                "available_tickets": 30,
                "going_count": 24,
                "series_name": "Arboretum Yoga",
                "start_offset_hours": 504,  # Week 3
                "duration_hours": 2,
            },
            # FOOD & DRINK (7 events)
            {
                "name": "Street Food Festival: Nairobi Eats",
                "description": "Two-day celebration of Nairobi's street food scene. 40+ vendors serving everything from mutura to bhajia to artisan burgers. Live music, beer garden, kids' zone. Cash and M-Pesa accepted. Go early on Saturday — Sunday runs out of the popular stalls by 3pm.",
                "category": "food-and-drink",
                "venue": "Ngong Racecourse",
                "neighbourhood": "Ngong Road",
                "location_tag": "nairobi",
                "lat": -1.3062,
                "lng": 36.7586,
                "price": Decimal("500"),
                "ticketing_enabled": True,
                "available_tickets": 800,
                "going_count": 564,
                "start_offset_hours": 168,  # Next week
                "duration_hours": 48,
                "has_gallery": True,
                "gallery_description": "Photos from last year's festival showing the variety of food stalls, live music performances, and the vibrant crowd. Includes close-ups of signature dishes from top vendors.",
            },
            {
                "name": "Wine & Cheese Pairing Masterclass",
                "description": "Guided tasting of 6 wines paired with artisanal cheeses from Kenya and beyond. Expert sommelier walks you through flavor profiles. Limited to 20 guests for intimate experience. Book early — this sells out within hours of announcement.",
                "category": "food-and-drink",
                "venue": "Alliance Française",
                "neighbourhood": "Westlands",
                "location_tag": "nairobi",
                "lat": -1.2644,
                "lng": 36.8078,
                "price": Decimal("3500"),
                "ticketing_enabled": True,
                "available_tickets": 5,  # Almost sold out
                "going_count": 18,
                "start_offset_hours": 240,  # Week 2
                "duration_hours": 3,
            },
            {
                "name": "Cultiva Farm: Sunset Supper Club",
                "description": "Farm-to-table 5-course dinner in the Tigoni hills. All ingredients sourced from the farm and neighboring smallholders. BYOB wine policy, corkage-free. Bring a warm layer — evenings get chilly at this altitude even in summer.",
                "category": "food-and-drink",
                "venue": "Cultiva Farm",
                "neighbourhood": "Tigoni",
                "location_tag": "naivasha",
                "lat": -1.1167,
                "lng": 36.6833,
                "price": Decimal("4500"),
                "ticketing_enabled": True,
                "available_tickets": 24,
                "going_count": 20,
                "start_offset_hours": 336,  # Week 2
                "duration_hours": 4,
            },
            {
                "name": "Nairobi Coffee Crawl",
                "description": "Guided walking tour visiting 5 of Nairobi's best specialty coffee roasters. Learn about Kenyan coffee production, cupping techniques, and brewing methods. Includes tastings at each stop. Wear comfortable shoes — it's 3km of walking.",
                "category": "food-and-drink",
                "venue": "Nairobi CBD",
                "neighbourhood": "CBD",
                "location_tag": "nairobi",
                "lat": -1.2864,
                "lng": 36.8172,
                "price": Decimal("2500"),
                "ticketing_enabled": True,
                "available_tickets": 15,
                "going_count": 12,
                "start_offset_hours": 96,  # This weekend
                "duration_hours": 3,
            },
            {
                "name": "Vegan Brunch Pop-Up at Spring Valley",
                "description": "Plant-based brunch featuring innovative takes on Kenyan classics. Think ugali made from purple sweet potato, coconut-based nyama choma substitute, and passion fruit mimosas. Outdoor seating in a garden setting. Limited capacity, no walk-ins.",
                "category": "food-and-drink",
                "venue": "Spring Valley Community Market",
                "neighbourhood": "Spring Valley",
                "location_tag": "nairobi",
                "lat": -1.2642,
                "lng": 36.7886,
                "price": Decimal("1800"),
                "ticketing_enabled": True,
                "available_tickets": 40,
                "going_count": 31,
                "start_offset_hours": 72,  # This weekend
                "duration_hours": 3,
            },
            {
                "name": "Craft Beer Tasting: East African Breweries",
                "description": "Sample 8 craft beers from Kenya, Tanzania, and Uganda. Meet the brewers, learn the stories behind each brew. Light bites included. Held at Brew Bistro's outdoor terrace. Come thirsty — it's generous pours.",
                "category": "food-and-drink",
                "venue": "Brew Bistro",
                "neighbourhood": "Westlands",
                "location_tag": "nairobi",
                "lat": -1.2650,
                "lng": 36.8100,
                "price": Decimal("2000"),
                "ticketing_enabled": True,
                "available_tickets": 35,
                "going_count": 28,
                "start_offset_hours": 504,  # Week 3
                "duration_hours": 3,
            },
            {
                "name": "BBQ & Beats Sunday Session",
                "description": "All-you-can-eat nyama choma buffet with live DJ. Goat, chicken, beef, and veggie options. Sides and salads included. Cash bar. Family-friendly until 6pm. Get the corner tables near the grill — freshest cuts come straight from there.",
                "category": "food-and-drink",
                "venue": "Carnivore Restaurant",
                "neighbourhood": "Langata",
                "location_tag": "nairobi",
                "lat": -1.3297,
                "lng": 36.8092,
                "price": Decimal("3200"),
                "ticketing_enabled": True,
                "available_tickets": 100,
                "going_count": 78,
                "start_offset_hours": 672,  # Week 4
                "duration_hours": 5,
            },
            # CULTURE & ARTS (7 events)
            {
                "name": "Contemporary Kenyan Art: New Voices Exhibition",
                "description": "Month-long exhibition featuring 15 emerging Kenyan visual artists. Paintings, sculpture, mixed media, and installations exploring themes of identity, urbanization, and climate. Opening reception this Friday with artist talks. Gallery is air-conditioned — a refuge from the midday heat.",
                "category": "culture-and-arts",
                "venue": "Circle Art Gallery",
                "neighbourhood": "Lavington",
                "location_tag": "nairobi",
                "lat": -1.2836,
                "lng": 36.7661,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 142,
                "start_offset_hours": 4,  # Tonight
                "duration_hours": 720,  # 30 days
                "more_details_url": "https://www.circleartgallery.com/",
                "has_gallery": True,
                "gallery_description": "Preview images of featured artworks including Wanjiru Kinyanjui's 'Urban Sprawl' series and Kamau Mwangi's sculptural installations. Gallery views and opening night photos from previous exhibitions.",
            },
            {
                "name": "Afro-Fusion Dance Workshop",
                "description": "3-hour intensive combining traditional African dance with contemporary and hip-hop styles. Beginner-friendly, no experience required. Wear comfortable athletic clothes and bring water. The GoDown studio gets warm — the ceiling fans help but it's still a workout.",
                "category": "culture-and-arts",
                "venue": "GoDown Arts Centre",
                "neighbourhood": "Ngara",
                "location_tag": "nairobi",
                "lat": -1.2699,
                "lng": 36.8387,
                "price": Decimal("1200"),
                "ticketing_enabled": True,
                "available_tickets": 25,
                "going_count": 18,
                "start_offset_hours": 96,  # This weekend
                "duration_hours": 3,
            },
            {
                "name": "Nairobi International Film Festival",
                "description": "Week-long showcase of African and international cinema. 40+ films across documentary, feature, and short categories. This year's focus: climate stories from the Global South. Opening night gala includes Q&A with filmmakers. Book multi-day passes for best value.",
                "category": "culture-and-arts",
                "venue": "Alliance Française",
                "neighbourhood": "Westlands",
                "location_tag": "nairobi",
                "lat": -1.2644,
                "lng": 36.8078,
                "price": Decimal("800"),
                "ticketing_enabled": True,
                "available_tickets": 180,
                "going_count": 156,
                "start_offset_hours": 336,  # Week 2
                "duration_hours": 168,  # 7 days
                "more_details_url": "https://www.alliance-francaise.or.ke",
                "has_gallery": True,
                "gallery_description": "Film stills from this year's featured selections and behind-the-scenes photos from the festival setup. Includes shots of past opening night galas and audience reactions.",
            },
            {
                "name": "Poetry Slam: Spoken Word Showcase",
                "description": "Open mic poetry night with featured performers from Nairobi's slam poetry scene. Sign up to perform or just enjoy the show. Cash bar and light snacks. The basement venue at PAWA has incredible acoustics — no mic needed for the intimate crowd.",
                "category": "culture-and-arts",
                "venue": "PAWA254",
                "neighbourhood": "Nairobi West",
                "location_tag": "nairobi",
                "lat": -1.3152,
                "lng": 36.8322,
                "price": Decimal("500"),
                "ticketing_enabled": True,
                "available_tickets": 60,
                "going_count": 42,
                "start_offset_hours": 168,  # Next week
                "duration_hours": 3,
            },
            {
                "name": "Kiswahili Theatre: Machozi ya Maendeleo",
                "description": "Original play performed in Kiswahili exploring gentrification and displacement in Nairobi's eastlands. Powerful ensemble cast. English subtitles projected. Two-act play with intermission. Seating is first-come — doors open 30 minutes before curtain.",
                "category": "culture-and-arts",
                "venue": "Kenya National Theatre",
                "neighbourhood": "CBD",
                "location_tag": "nairobi",
                "lat": -1.2781,
                "lng": 36.8210,
                "price": Decimal("1000"),
                "ticketing_enabled": True,
                "available_tickets": 150,
                "going_count": 89,
                "start_offset_hours": 240,  # Week 2
                "duration_hours": 3,
            },
            {
                "name": "Beading & Jewelry Making Class",
                "description": "Learn traditional Maasai beading techniques and create your own jewelry piece to take home. All materials provided. Taught by artisans from the Maasai Market collective. Small class size for personalized instruction. Bring reading glasses if you need them — the beadwork is detailed.",
                "category": "culture-and-arts",
                "venue": "The Hub Karen",
                "neighbourhood": "Karen",
                "location_tag": "nairobi",
                "lat": -1.3218,
                "lng": 36.7073,
                "price": Decimal("2500"),
                "ticketing_enabled": True,
                "available_tickets": 12,
                "going_count": 9,
                "start_offset_hours": 504,  # Week 3
                "duration_hours": 3,
            },
            {
                "name": "Jazz Fusion Concert: Nairobi Horns Project",
                "description": "The legendary Nairobi Horns Project performs an evening of Afro-jazz fusion. Expect improvisation, call-and-response, and infectious rhythms. Seated venue, limited standing room. Cash bar, no food service. This group rarely plays Nairobi anymore — catch them while you can.",
                "category": "culture-and-arts",
                "venue": "Alliance Française",
                "neighbourhood": "Westlands",
                "location_tag": "nairobi",
                "lat": -1.2644,
                "lng": 36.8078,
                "price": Decimal("1500"),
                "ticketing_enabled": True,
                "available_tickets": 85,
                "going_count": 71,
                "start_offset_hours": 672,  # Week 4
                "duration_hours": 3,
            },
            # TALKS & IDEAS (6 events)
            {
                "name": "Tech Startup Pitch Night",
                "description": "Watch 8 Kenyan startups pitch their ideas to a panel of investors. Followed by networking session with founders, VCs, and the tech community. Free entry, drink minimum KES 500. Bring business cards — the networking after is where the real deals happen.",
                "category": "talks-and-ideas",
                "venue": "PAWA254",
                "neighbourhood": "Nairobi West",
                "location_tag": "nairobi",
                "lat": -1.3152,
                "lng": 36.8322,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 98,
                "start_offset_hours": 168,  # Next week
                "duration_hours": 3,
                "more_details_url": "https://pawa254.org",
            },
            {
                "name": "Climate Change in East Africa: A Panel Discussion",
                "description": "Environmental scientists, policymakers, and activists discuss climate adaptation strategies for Kenya. Moderated Q&A follows. Light refreshments served. The museum auditorium AC is aggressive — bring a light jacket even on hot days.",
                "category": "talks-and-ideas",
                "venue": "Nairobi National Museum",
                "neighbourhood": "CBD",
                "location_tag": "nairobi",
                "lat": -1.2687,
                "lng": 36.8143,
                "price": Decimal("500"),
                "ticketing_enabled": True,
                "available_tickets": 120,
                "going_count": 87,
                "start_offset_hours": 240,  # Week 2
                "duration_hours": 2,
            },
            {
                "name": "Book Club: Ngũgĩ wa Thiong'o Discussion",
                "description": "Monthly book club discusses 'The River Between' and Ngũgĩ's influence on African literature. Open to all, come prepared to share your thoughts. Coffee and snacks provided. The discussion gets lively — if you haven't finished the book, you'll still enjoy the conversation.",
                "category": "talks-and-ideas",
                "venue": "Alliance Française",
                "neighbourhood": "Westlands",
                "location_tag": "nairobi",
                "lat": -1.2644,
                "lng": 36.8078,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 34,
                "series_name": "Monthly Book Club",
                "start_offset_hours": 336,  # Week 2
                "duration_hours": 2,
                "more_details_url": "https://www.alliance-francaise.or.ke",
            },
            {
                "name": "Women in Business Breakfast",
                "description": "Networking breakfast for women entrepreneurs and professionals. Guest speaker: CEO of Safaricom. Panel on access to capital, work-life balance, and building networks. Continental breakfast included. Registration closes 24 hours before — no walk-ins due to catering.",
                "category": "talks-and-ideas",
                "venue": "Radisson Blu Hotel",
                "neighbourhood": "Upper Hill",
                "location_tag": "nairobi",
                "lat": -1.2901,
                "lng": 36.8205,
                "price": Decimal("1500"),
                "ticketing_enabled": True,
                "available_tickets": 80,
                "going_count": 64,
                "start_offset_hours": 504,  # Week 3
                "duration_hours": 3,
            },
            {
                "name": "Photography Workshop: Street Photography Nairobi",
                "description": "Half-day workshop covering street photography techniques. Morning classroom session followed by guided walk through Nairobi streets. Bring your camera (phone cameras welcome). Lunch included. Instructor is a Magnum photographer — rare opportunity for this level of teaching.",
                "category": "talks-and-ideas",
                "venue": "GoDown Arts Centre",
                "neighbourhood": "Ngara",
                "location_tag": "nairobi",
                "lat": -1.2699,
                "lng": 36.8387,
                "price": Decimal("3500"),
                "ticketing_enabled": True,
                "available_tickets": 15,
                "going_count": 12,
                "start_offset_hours": 672,  # Week 4
                "duration_hours": 5,
            },
            {
                "name": "TEDx Nairobi: Ideas Worth Spreading",
                "description": "Full-day conference featuring 12 speakers on innovation, culture, and social change. Networking breaks, lunch, and evening reception included. Past speakers include Lupita Nyong'o and Juliani. Book early for early-bird discount — prices rise 2 weeks before event.",
                "category": "talks-and-ideas",
                "venue": "Sarit Centre",
                "neighbourhood": "Westlands",
                "location_tag": "nairobi",
                "lat": -1.2617,
                "lng": 36.7910,
                "price": Decimal("5000"),
                "ticketing_enabled": True,
                "available_tickets": 200,
                "going_count": 178,
                "start_offset_hours": 840,  # Week 5
                "duration_hours": 8,
            },
            # WORKSHOPS & CLASSES (6 events)
            {
                "name": "Ceramics: Handbuilding Basics",
                "description": "Learn coil and slab techniques to create functional pottery. No experience needed. All materials and tools provided. Pieces will be fired and glazed — ready for pickup in 3 weeks. Wear clothes that can get dirty — clay stains are permanent.",
                "category": "workshops-and-classes",
                "venue": "GoDown Arts Centre",
                "neighbourhood": "Ngara",
                "location_tag": "nairobi",
                "lat": -1.2699,
                "lng": 36.8387,
                "price": Decimal("2800"),
                "ticketing_enabled": True,
                "available_tickets": 10,
                "going_count": 8,
                "start_offset_hours": 96,  # This weekend
                "duration_hours": 4,
            },
            {
                "name": "Kiswahili for Beginners: Conversational Class",
                "description": "4-week course in basic Kiswahili. One 2-hour session per week. Focused on conversational skills and common phrases. Small class size, interactive exercises. Workbook provided. Classes fill fast with expats — locals welcome too if you never formally learned.",
                "category": "workshops-and-classes",
                "venue": "Alliance Française",
                "neighbourhood": "Westlands",
                "location_tag": "nairobi",
                "lat": -1.2644,
                "lng": 36.8078,
                "price": Decimal("4000"),
                "ticketing_enabled": True,
                "available_tickets": 12,
                "going_count": 10,
                "start_offset_hours": 168,  # Next week
                "duration_hours": 8,
            },
            {
                "name": "Bread Making Workshop: Sourdough & Artisan Loaves",
                "description": "Full-day workshop learning to make sourdough starter and bake artisan bread. Hands-on throughout. Each participant bakes 2 loaves to take home. Lunch included. Held at a working bakery — you'll leave smelling like fresh bread.",
                "category": "workshops-and-classes",
                "venue": "Spring Valley Community Market",
                "neighbourhood": "Spring Valley",
                "location_tag": "nairobi",
                "lat": -1.2642,
                "lng": 36.7886,
                "price": Decimal("3500"),
                "ticketing_enabled": True,
                "available_tickets": 8,
                "going_count": 7,
                "start_offset_hours": 240,  # Week 2
                "duration_hours": 6,
            },
            {
                "name": "Digital Marketing for Small Business",
                "description": "Half-day intensive covering social media strategy, content creation, and analytics. Bring your laptop. Case studies from Kenyan businesses. Coffee and lunch included. The instructor worked at Safaricom for 10 years — practical insights over theory.",
                "category": "workshops-and-classes",
                "venue": "PAWA254",
                "neighbourhood": "Nairobi West",
                "location_tag": "nairobi",
                "lat": -1.3152,
                "lng": 36.8322,
                "price": Decimal("2500"),
                "ticketing_enabled": True,
                "available_tickets": 25,
                "going_count": 19,
                "start_offset_hours": 336,  # Week 2
                "duration_hours": 4,
            },
            {
                "name": "Batik & Tie-Dye: Fabric Art Workshop",
                "description": "Create your own wearable art using traditional batik and tie-dye techniques. Bring a white cotton item (t-shirt, scarf, pillowcase). All dyes and tools provided. Outdoor workspace — dress for mess and sun. Takes 2 hours to fully dry before you can take it home.",
                "category": "workshops-and-classes",
                "venue": "The Hub Karen",
                "neighbourhood": "Karen",
                "location_tag": "nairobi",
                "lat": -1.3218,
                "lng": 36.7073,
                "price": Decimal("1800"),
                "ticketing_enabled": True,
                "available_tickets": 15,
                "going_count": 11,
                "start_offset_hours": 504,  # Week 3
                "duration_hours": 3,
            },
            {
                "name": "Urban Gardening: Container Vegetable Growing",
                "description": "Learn to grow vegetables in small spaces — balconies, patios, windowsills. Covers seed selection, soil, watering, and pest management. Each participant plants a starter container to take home. Perfect for apartment dwellers who want to grow their own kale and spinach.",
                "category": "workshops-and-classes",
                "venue": "Cultiva Farm",
                "neighbourhood": "Tigoni",
                "location_tag": "naivasha",
                "lat": -1.1167,
                "lng": 36.6833,
                "price": Decimal("2000"),
                "ticketing_enabled": True,
                "available_tickets": 20,
                "going_count": 16,
                "start_offset_hours": 672,  # Week 4
                "duration_hours": 3,
            },
            # MARKETS & POPUPS (4 events)
            {
                "name": "Maasai Market Showcase",
                "description": "Weekly rotating market featuring Maasai beadwork, fabrics, carvings, and crafts. Over 50 vendors. Haggling expected and encouraged. Proceeds support artisan cooperatives. Bring cash — most vendors don't take M-Pesa, and the ATM runs out on busy days.",
                "category": "markets-and-popups",
                "venue": "Village Market",
                "neighbourhood": "Gigiri",
                "location_tag": "nairobi",
                "lat": -1.2300,
                "lng": 36.8037,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 203,
                "series_name": "Weekly Maasai Market",
                "start_offset_hours": 72,  # This weekend
                "duration_hours": 6,
                "more_details_url": "https://villagemarket-kenya.com",
            },
            {
                "name": "Farmers Market: Organic Produce & Artisan Goods",
                "description": "Monthly farmers market with organic vegetables, homemade jams, fresh bread, honey, and crafts. Live music, food trucks, kids' activities. Free entry. Arrive early — the best produce sells out by 10am, especially during dry season.",
                "category": "markets-and-popups",
                "venue": "Spring Valley Community Market",
                "neighbourhood": "Spring Valley",
                "location_tag": "nairobi",
                "lat": -1.2642,
                "lng": 36.7886,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 156,
                "series_name": "Monthly Farmers Market",
                "start_offset_hours": 96,  # This weekend
                "duration_hours": 4,
                "more_details_url": "https://pursuit.app/demo",
            },
            {
                "name": "Vintage Fashion & Vinyl Records Popup",
                "description": "Curated vintage clothing and record sale. 10 vendors with 60s-90s fashion and rare East African vinyl. Try-on mirrors available. Cash and M-Pesa. DJ spinning records all day. The upstairs section has the best clothing picks — less picked over than the ground floor.",
                "category": "markets-and-popups",
                "venue": "Alchemist Bar",
                "neighbourhood": "Westlands",
                "location_tag": "nairobi",
                "lat": -1.2673,
                "lng": 36.8073,
                "price": Decimal("0"),
                "ticketing_enabled": False,
                "available_tickets": None,
                "going_count": 87,
                "start_offset_hours": 168,  # Next week
                "duration_hours": 6,
                "more_details_url": "https://alchemistbar.co.ke/events",
            },
            {
                "name": "Holiday Gift Bazaar",
                "description": "Two-day shopping event with 60+ local artisans and makers. Jewelry, home decor, skincare, gourmet foods, children's items. Gift wrapping available. Live entertainment. Parking can be a nightmare — consider an Uber or arrive before 11am.",
                "category": "markets-and-popups",
                "venue": "The Hub Karen",
                "neighbourhood": "Karen",
                "location_tag": "nairobi",
                "lat": -1.3218,
                "lng": 36.7073,
                "price": Decimal("200"),
                "ticketing_enabled": True,
                "available_tickets": 500,
                "going_count": 342,
                "start_offset_hours": 504,  # Week 3
                "duration_hours": 16,
            },
            # TRAVEL (4 events)
            {
                "name": "Lamu Cultural Heritage Weekend",
                "description": "3-day guided tour of Lamu Old Town — UNESCO World Heritage Site. Includes dhow sailing, Swahili cooking class, spice market visit, and historical walking tour. Accommodation and most meals included. Book flights separately. November to March is the best weather — less humid than summer.",
                "category": "travel",
                "venue": "Lamu Old Town",
                "neighbourhood": "Lamu",
                "location_tag": "mombasa",
                "lat": -2.2717,
                "lng": 40.9020,
                "price": Decimal("18000"),
                "ticketing_enabled": True,
                "available_tickets": 12,
                "going_count": 9,
                "start_offset_hours": 672,  # Week 4
                "duration_hours": 72,
            },
            {
                "name": "Diani Beach Yoga Retreat",
                "description": "5-day wellness retreat on Diani Beach. Daily yoga, meditation, healthy meals, and spa treatments. Optional activities: snorkeling, stand-up paddleboarding, dhow sunset cruise. Airport transfers from Ukunda included. Shared and private room options.",
                "category": "travel",
                "venue": "Diani Beach",
                "neighbourhood": "Diani",
                "location_tag": "mombasa",
                "lat": -4.2894,
                "lng": 39.5788,
                "price": Decimal("35000"),
                "ticketing_enabled": True,
                "available_tickets": 8,
                "going_count": 6,
                "start_offset_hours": 1008,  # Week 6
                "duration_hours": 120,
                "has_gallery": True,
                "gallery_description": "Photos of the beachfront yoga pavilion, accommodation options, and previous retreat activities. Includes shots of the spa, dining area, and beach at sunset.",
            },
            {
                "name": "Mt. Kenya Climbing Expedition: Sirimon Route",
                "description": "5-day trek to Point Lenana (4,985m), Mt. Kenya's third-highest peak. All camping gear, porters, and meals included. Experienced mountain guide. Moderate to challenging fitness required. Acclimatization built into the itinerary — but altitude sickness is still possible, know the signs.",
                "category": "travel",
                "venue": "Mt. Kenya National Park",
                "neighbourhood": "Nanyuki",
                "location_tag": "nairobi",
                "lat": -0.1521,
                "lng": 37.3084,
                "price": Decimal("42000"),
                "ticketing_enabled": True,
                "available_tickets": 6,
                "going_count": 5,
                "start_offset_hours": 840,  # Week 5
                "duration_hours": 120,
            },
            {
                "name": "Maasai Mara Safari: Great Migration",
                "description": "3-day safari focused on witnessing the Great Migration river crossings. Game drives morning and evening, luxury tented camp accommodation. All meals and park fees included. Nairobi pickup/drop-off. August and September are peak migration — book 6 months ahead.",
                "category": "travel",
                "venue": "Maasai Mara National Reserve",
                "neighbourhood": "Mara",
                "location_tag": "nairobi",
                "lat": -1.5014,
                "lng": 35.1440,
                "price": Decimal("55000"),
                "ticketing_enabled": True,
                "available_tickets": 10,
                "going_count": 8,
                "start_offset_hours": 1176,  # Week 7
                "duration_hours": 72,
                "has_gallery": True,
                "gallery_description": "Safari photos from previous trips showing wildlife encounters, river crossings, and camp accommodations. Includes dawn and dusk shots of the Mara landscape.",
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
                },
            )
            event.category.set([category])
            events.append(event)

        return events

    def _seed_user_interactions(self, events):
        """Create diverse user interactions for varied recommendations"""
        users = list(User.objects.all())

        if not users:
            self.stdout.write(self.style.WARNING("No users found — skipping interaction seeding"))
            return 0

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

        # Create different interest patterns per user
        interaction_count = 0

        for user in users:
            # Each user saves 3-8 events based on different patterns
            import random

            random.seed(str(user.id))  # Deterministic but varied per user

            # Random interest pattern
            interest_categories = random.sample(
                [
                    "concerts-and-nightlife",
                    "outdoors-and-active",
                    "food-and-drink",
                    "culture-and-arts",
                    "talks-and-ideas",
                    "workshops-and-classes",
                    "markets-and-popups",
                    "travel",
                ],
                k=random.randint(2, 4),
            )

            # Filter events by user's interests
            interested_events = [
                e
                for e in events
                if e.category.first() and name_to_slug.get(e.category.first().name) in interest_categories
            ]

            # Save 3-8 random events from their interest categories
            events_to_save = random.sample(interested_events, min(random.randint(3, 8), len(interested_events)))

            for event in events_to_save:
                UserEvents.objects.get_or_create(user=user, event=event)
                interaction_count += 1

                # Update going_count on the event
                event.going_count += 1
                event.save(update_fields=["going_count"])

        return interaction_count

    def _seed_editors_picks(self, events):
        """Create editor's picks for different locations and time periods"""
        now = timezone.now()

        # Select strong events with good descriptions for editor's picks
        concerts_events = [e for e in events if e.category.first() and e.category.first().name == "Concerts & Nightlife"]
        culture_events = [e for e in events if e.category.first() and e.category.first().name == "Culture & Arts"]
        food_events = [e for e in events if e.category.first() and e.category.first().name == "Food & Drink"]

        picks_data = [
            {
                "event": concerts_events[0] if concerts_events else events[0],
                "location_tag": "nairobi",
                "active_from": now,
                "active_until": now + timedelta(days=7),
                "curator_note": "Nairobi's most iconic outdoor music festival. The vibe is unmatched — arrive early for the best lawn spots.",
                "curator_name": "Kamau, Pursuit",
                "position": 1,
            },
            {
                "event": culture_events[0] if culture_events else events[1],
                "location_tag": "nairobi",
                "active_from": now + timedelta(days=7),
                "active_until": now + timedelta(days=14),
                "curator_note": "A must-see exhibition showcasing Kenya's emerging art scene. The opening reception is always electric.",
                "curator_name": "Pursuit team",
                "position": 1,
            },
            {
                "event": food_events[0] if food_events else events[2],
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

    def _seed_trips(self, events):
        """Create trips for some users with associated events"""
        users = list(User.objects.all())

        if not users:
            return 0

        import random

        now = timezone.now()
        # Get travel events for trips
        travel_events = [e for e in events if e.category.first() and e.category.first().name == "Travel"]

        trips_data = [
            {
                "name": "Coastal Getaway: Lamu & Diani",
                "destination": "Lamu & Diani Beach",
                "start_date": now + timedelta(days=21),
                "end_date": now + timedelta(days=28),
                "image": "https://images.unsplash.com/photo-1559827260-dc66d52bef19",
            },
            {
                "name": "Mt. Kenya Adventure",
                "destination": "Mt. Kenya & Nanyuki",
                "start_date": now + timedelta(days=28),
                "end_date": now + timedelta(days=33),
                "image": "https://images.unsplash.com/photo-1589553416260-f586c8f1514f",
            },
            {
                "name": "Maasai Mara Safari",
                "destination": "Maasai Mara",
                "start_date": now + timedelta(days=14),
                "end_date": now + timedelta(days=17),
                "image": "https://images.unsplash.com/photo-1516426122078-c23e76319801",
            },
        ]

        trips_count = 0

        # Assign trips to different users
        for idx, trip_data in enumerate(trips_data):
            if idx >= len(users):
                break

            user = users[idx]

            trip, created = Trip.objects.update_or_create(
                user=user,
                name=trip_data["name"],
                defaults={
                    "destination": trip_data["destination"],
                    "start_date": trip_data["start_date"],
                    "end_date": trip_data["end_date"],
                    "image": trip_data["image"],
                },
            )

            # Add 1-2 travel events to each trip
            trip_events = random.sample(travel_events, min(2, len(travel_events)))
            for event in trip_events:
                trip.events.add(event)

            trips_count += 1

        return trips_count
