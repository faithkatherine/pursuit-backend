from datetime import timedelta

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.models import Category
from apps.events.models import Event

# Real coordinates for cities
COORDS = {
    "Nairobi": Point(36.8219, -1.2921, srid=4326),
    "Mombasa": Point(39.6682, -4.0435, srid=4326),
    "Kisumu": Point(34.7617, -0.1022, srid=4326),
    "Nakuru": Point(36.0800, -0.3031, srid=4326),
    "Malindi": Point(40.1169, -3.2138, srid=4326),
    "Lamu": Point(40.9020, -2.2717, srid=4326),
    "Diani": Point(39.5833, -4.3167, srid=4326),
    "Naivasha": Point(36.4310, -0.7172, srid=4326),
    "London": Point(-0.1276, 51.5074, srid=4326),
    "Manchester": Point(-2.2426, 53.4808, srid=4326),
    "Edinburgh": Point(-3.1883, 55.9533, srid=4326),
    "Birmingham": Point(-1.8904, 52.4862, srid=4326),
    "Atlanta": Point(-84.3880, 33.7490, srid=4326),
    "New York": Point(-74.0060, 40.7128, srid=4326),
    "Los Angeles": Point(-118.2437, 34.0522, srid=4326),
}

TIMEZONES = {
    "Nairobi": "Africa/Nairobi",
    "Mombasa": "Africa/Nairobi",
    "Kisumu": "Africa/Nairobi",
    "Nakuru": "Africa/Nairobi",
    "Malindi": "Africa/Nairobi",
    "Lamu": "Africa/Nairobi",
    "Diani": "Africa/Nairobi",
    "Naivasha": "Africa/Nairobi",
    "London": "Europe/London",
    "Manchester": "Europe/London",
    "Edinburgh": "Europe/London",
    "Birmingham": "Europe/London",
    "Atlanta": "America/New_York",
    "New York": "America/New_York",
    "Los Angeles": "America/Los_Angeles",
}

# Unsplash placeholder images by category
_U = "https://images.unsplash.com/photo-"
_Q = "?auto=format&fit=crop&q=80&w=800"
IMAGES = {
    "Travel": f"{_U}1488085061387-422e29b40080{_Q}",
    "Adventure": f"{_U}1533692328991-08159ff19fca{_Q}",
    "Food & Drink": f"{_U}1504674900247-0877df9cc836{_Q}",
    "Culture": f"{_U}1533669955142-6a73332af4db{_Q}",
    "Learning": f"{_U}1524178232363-1fb2b075b655{_Q}",
    "Sports": f"{_U}1461896836934-bd45ba8ce684{_Q}",
    "Music & Events": f"{_U}1459749411175-04bf5292ceea{_Q}",
    "Nature": f"{_U}1441974231531-c6227db76b6e{_Q}",
}


def _dt(days_offset, hour=9):
    """Return a datetime `days_offset` days from now at given hour."""
    return timezone.now().replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=days_offset)


# Each entry: (name, description, city, categories, days_offset, duration_days)
# duration_days=0 means single-day event; >0 means multi-day
EVENTS_DATA = [
    # ── Travel (5 Kenya, 2 UK, 1 US) ────────────────────────────────
    (
        "Magical Kenya Travel Expo",
        "East Africa's premier travel trade fair showcasing tourism " "destinations and hospitality services.",
        "Nairobi",
        ["Travel"],
        30,
        3,
    ),
    (
        "Lamu Cultural Festival",
        "A vibrant celebration of Swahili culture with dhow races, "
        "donkey races, and traditional music on Lamu Island.",
        "Lamu",
        ["Travel", "Culture"],
        45,
        4,
    ),
    (
        "Mombasa Travel & Tourism Fair",
        "Discover coastal Kenya's beach resorts, water sports, and " "heritage tourism at this annual coastal expo.",
        "Mombasa",
        ["Travel"],
        60,
        2,
    ),
    (
        "Kenya Camping & Caravan Show",
        "Explore the latest camping gear, overland vehicles, and safari " "camping experiences across Kenya.",
        "Nairobi",
        ["Travel", "Adventure"],
        90,
        3,
    ),
    (
        "Diani Beach Festival",
        "A week-long festival celebrating Diani's stunning beaches with "
        "kite-surfing demos, beach volleyball, and sundowner events.",
        "Diani",
        ["Travel", "Adventure"],
        75,
        5,
    ),
    (
        "World Travel Market London",
        "The leading global event for the travel industry, connecting " "travel professionals from around the world.",
        "London",
        ["Travel"],
        120,
        3,
    ),
    (
        "Edinburgh Fringe Festival Travel Showcase",
        "Explore Scotland's travel offerings alongside the world's " "largest arts festival.",
        "Edinburgh",
        ["Travel", "Culture"],
        150,
        2,
    ),
    (
        "Atlanta Travel & Adventure Show",
        "The Southeast's biggest travel show featuring destinations, " "gear, and expert travel advice.",
        "Atlanta",
        ["Travel"],
        100,
        2,
    ),
    # ── Adventure (5 Kenya, 2 UK, 1 US) ─────────────────────────────
    (
        "Mount Kenya Ultra Trail",
        "A grueling ultra-marathon around Mount Kenya through forests, " "moorlands, and high-altitude terrain.",
        "Nakuru",
        ["Adventure", "Sports"],
        35,
        2,
    ),
    (
        "Hell's Gate Rock Climbing Weekend",
        "Guided rock climbing and gorge walking in Hell's Gate " "National Park near Lake Naivasha.",
        "Naivasha",
        ["Adventure"],
        20,
        2,
    ),
    (
        "Diani Skydiving Experience",
        "Tandem skydiving over the turquoise waters of the Indian Ocean " "at Diani Beach.",
        "Diani",
        ["Adventure"],
        50,
        0,
    ),
    (
        "Masai Mara Balloon Safari",
        "A sunrise hot air balloon ride over the Masai Mara with " "champagne bush breakfast.",
        "Nairobi",
        ["Adventure", "Nature"],
        40,
        0,
    ),
    (
        "Tana River White Water Rafting",
        "Exciting white-water rafting on the Tana River with Class III " "and IV rapids near Sagana.",
        "Nairobi",
        ["Adventure"],
        25,
        0,
    ),
    (
        "Lake District Adventure Weekend",
        "Kayaking, fell running, and wild camping in England's Lake " "District National Park.",
        "Manchester",
        ["Adventure", "Nature"],
        55,
        2,
    ),
    (
        "Scottish Highlands Survival Course",
        "A wilderness survival course in the Scottish Highlands covering " "fire-making, foraging, and navigation.",
        "Edinburgh",
        ["Adventure", "Learning"],
        80,
        3,
    ),
    (
        "NYC Urban Adventure Race",
        "A city-wide adventure race through New York's boroughs " "combining running, cycling, and problem-solving.",
        "New York",
        ["Adventure", "Sports"],
        65,
        0,
    ),
    # ── Food & Drink (5 Kenya, 2 UK, 1 US) ──────────────────────────
    (
        "Nairobi Restaurant Week",
        "Two weeks of prix-fixe menus at Nairobi's top restaurants " "showcasing Kenyan and international cuisine.",
        "Nairobi",
        ["Food & Drink"],
        15,
        14,
    ),
    (
        "Mombasa Street Food Festival",
        "Taste the best of coastal Kenyan street food: biryani, " "viazi karai, mahamri, and fresh seafood.",
        "Mombasa",
        ["Food & Drink", "Culture"],
        42,
        3,
    ),
    (
        "Nairobi Coffee Festival",
        "Celebrate Kenya's world-renowned coffee with tastings, " "barista competitions, and farm-to-cup tours.",
        "Nairobi",
        ["Food & Drink"],
        70,
        2,
    ),
    (
        "Kisumu Fish Festival",
        "A lakeside celebration of Lake Victoria's fishing heritage " "with fresh tilapia and omena tastings.",
        "Kisumu",
        ["Food & Drink", "Culture"],
        55,
        2,
    ),
    (
        "Malindi Italian Food Fair",
        "Malindi's Italian community hosts a food fair blending " "Italian and Swahili coastal flavours.",
        "Malindi",
        ["Food & Drink"],
        85,
        2,
    ),
    (
        "London Wine & Spirits Festival",
        "Sample wines and spirits from over 300 producers at this " "premier London tasting event.",
        "London",
        ["Food & Drink"],
        95,
        3,
    ),
    (
        "Birmingham Curry Festival",
        "A celebration of Birmingham's iconic curry scene with " "cooking demos, tastings, and live music.",
        "Birmingham",
        ["Food & Drink", "Culture"],
        110,
        2,
    ),
    (
        "Atlanta Food & Wine Festival",
        "The South's premier food festival featuring celebrity chefs, " "tasting tents, and Southern cooking classes.",
        "Atlanta",
        ["Food & Drink"],
        130,
        3,
    ),
    # ── Culture (5 Kenya, 2 UK, 1 US) ───────────────────────────────
    (
        "Nairobi Art Week",
        "A week of gallery openings, studio tours, and public art "
        "installations across Nairobi's creative districts.",
        "Nairobi",
        ["Culture"],
        22,
        7,
    ),
    (
        "Kisumu Suba Cultural Festival",
        "A celebration of the Suba people's traditions with dance, "
        "music, and storytelling on the shores of Lake Victoria.",
        "Kisumu",
        ["Culture"],
        48,
        2,
    ),
    (
        "Mombasa Swahili Heritage Walk",
        "Guided heritage walks through Mombasa Old Town exploring "
        "Fort Jesus, Swahili architecture, and local crafts.",
        "Mombasa",
        ["Culture", "Learning"],
        18,
        0,
    ),
    (
        "Nakuru Blankets & Wine",
        "An outdoor picnic-style event featuring live bands, DJs, " "and local food vendors in Nakuru's Hyrax Hill.",
        "Nakuru",
        ["Culture", "Music & Events"],
        32,
        0,
    ),
    (
        "Kenya Fashion Week",
        "Showcasing African fashion designers with runway shows, " "pop-up markets, and industry workshops.",
        "Nairobi",
        ["Culture"],
        105,
        4,
    ),
    (
        "London African Film Festival",
        "Screenings, panels, and Q&As celebrating the best of " "African cinema at BFI Southbank.",
        "London",
        ["Culture"],
        140,
        10,
    ),
    (
        "Manchester International Festival",
        "A biennial festival of original new work from across the " "arts including theatre, music, and visual art.",
        "Manchester",
        ["Culture", "Music & Events"],
        160,
        18,
    ),
    (
        "Harlem Cultural Festival NYC",
        "Celebrating Harlem's rich cultural heritage with live " "performances, art exhibits, and soul food.",
        "New York",
        ["Culture", "Music & Events"],
        115,
        2,
    ),
    # ── Learning (5 Kenya, 2 UK, 1 US) ──────────────────────────────
    (
        "Nairobi Tech Week",
        "East Africa's largest tech conference with workshops on AI, " "fintech, and mobile innovation.",
        "Nairobi",
        ["Learning"],
        28,
        5,
    ),
    (
        "Swahili Language Immersion Lamu",
        "A week-long Swahili language course on Lamu Island combining " "classroom learning with cultural immersion.",
        "Lamu",
        ["Learning", "Culture"],
        60,
        7,
    ),
    (
        "Wildlife Photography Masterclass",
        "A hands-on photography workshop in Nakuru National Park led " "by award-winning wildlife photographers.",
        "Nakuru",
        ["Learning", "Nature"],
        38,
        3,
    ),
    (
        "Kisumu Entrepreneurship Bootcamp",
        "An intensive bootcamp for aspiring entrepreneurs covering "
        "business planning, funding, and digital marketing.",
        "Kisumu",
        ["Learning"],
        72,
        5,
    ),
    (
        "Mombasa Marine Biology Workshop",
        "Learn about coral reef conservation and marine ecosystems " "at the Kenya Marine Research Institute.",
        "Mombasa",
        ["Learning", "Nature"],
        88,
        3,
    ),
    (
        "Oxford Creative Writing Retreat",
        "A weekend writing retreat at an Oxford college with sessions " "on fiction, poetry, and memoir.",
        "London",
        ["Learning"],
        125,
        2,
    ),
    (
        "Edinburgh Science Festival",
        "Hands-on science workshops, talks, and exhibitions for " "curious minds of all ages.",
        "Edinburgh",
        ["Learning"],
        145,
        14,
    ),
    (
        "Atlanta Startup Summit",
        "Workshops and mentoring sessions connecting founders with " "investors and industry leaders.",
        "Atlanta",
        ["Learning"],
        98,
        2,
    ),
    # ── Sports (5 Kenya, 2 UK, 1 US) ────────────────────────────────
    (
        "Nairobi Marathon",
        "The annual Nairobi Marathon attracting elite runners and " "amateurs through the city's scenic routes.",
        "Nairobi",
        ["Sports"],
        44,
        0,
    ),
    (
        "Diani Beach Triathlon",
        "Swim, cycle, and run along the stunning Diani coastline " "in this popular multi-sport event.",
        "Diani",
        ["Sports", "Adventure"],
        58,
        0,
    ),
    (
        "Kenya Sevens Rugby Festival",
        "The electrifying Kenya Sevens rugby tournament with live " "music, food, and family entertainment.",
        "Nairobi",
        ["Sports", "Music & Events"],
        36,
        2,
    ),
    (
        "Lewa Safari Marathon",
        "Run a marathon through a wildlife conservancy alongside " "giraffes, zebras, and elephants.",
        "Nairobi",
        ["Sports", "Nature"],
        82,
        0,
    ),
    (
        "Kisumu Boat Race",
        "Annual boat racing on Lake Victoria with rowing, sailing, " "and traditional dhow competitions.",
        "Kisumu",
        ["Sports"],
        68,
        0,
    ),
    (
        "London Marathon Expo",
        "The official expo for the London Marathon with gear, " "nutrition, and running workshops.",
        "London",
        ["Sports"],
        135,
        3,
    ),
    (
        "Manchester City Football Experience",
        "Behind-the-scenes stadium tours, coaching clinics, and " "match-day experiences at the Etihad.",
        "Manchester",
        ["Sports"],
        52,
        0,
    ),
    (
        "NYC Basketball Classic",
        "An outdoor basketball tournament in Harlem featuring " "streetball legends and rising stars.",
        "New York",
        ["Sports"],
        78,
        2,
    ),
    # ── Music & Events (5 Kenya, 2 UK, 1 US) ────────────────────────
    (
        "Koroga Festival Nairobi",
        "Kenya's favourite outdoor music festival blending Afrobeats, " "jazz, and soul with gourmet food trucks.",
        "Nairobi",
        ["Music & Events"],
        26,
        0,
    ),
    (
        "Sauti za Busara Mombasa Satellite",
        "A satellite edition of the Sauti za Busara music festival " "bringing East African sounds to the coast.",
        "Mombasa",
        ["Music & Events", "Culture"],
        62,
        3,
    ),
    (
        "Nakuru Jazz & Blues Night",
        "A monthly jazz and blues night featuring Kenyan and " "international musicians at Nakuru's Lake Basin.",
        "Nakuru",
        ["Music & Events"],
        14,
        0,
    ),
    (
        "Malindi Beach Music Festival",
        "A beachside music festival with reggae, Afro-pop, and " "Taarab performances under the stars.",
        "Malindi",
        ["Music & Events"],
        92,
        2,
    ),
    (
        "Nairobi Acoustic Sessions",
        "Intimate acoustic performances by Kenyan singer-songwriters " "at Nairobi's rooftop venues.",
        "Nairobi",
        ["Music & Events"],
        10,
        0,
    ),
    (
        "Notting Hill Carnival Warm-Up",
        "Pre-carnival live music, steel pan workshops, and Caribbean " "food in West London.",
        "London",
        ["Music & Events", "Culture"],
        155,
        2,
    ),
    (
        "Edinburgh Hogmanay Concert",
        "New Year's Eve concert and fireworks celebration in " "Edinburgh's Princes Street Gardens.",
        "Edinburgh",
        ["Music & Events"],
        180,
        0,
    ),
    (
        "Atlanta Jazz Festival",
        "One of the largest free jazz festivals in the US, held " "annually in Piedmont Park.",
        "Atlanta",
        ["Music & Events"],
        108,
        3,
    ),
    # ── Nature (5 Kenya, 2 UK, 1 US) ────────────────────────────────
    (
        "Great Wildebeest Migration Viewing",
        "Guided safari viewing of the Great Migration at the Masai " "Mara with expert naturalist guides.",
        "Nairobi",
        ["Nature"],
        50,
        3,
    ),
    (
        "Lake Nakuru Flamingo Walk",
        "A guided birding walk to see the famous flamingos and " "pelicans of Lake Nakuru National Park.",
        "Nakuru",
        ["Nature"],
        16,
        0,
    ),
    (
        "Arabuko-Sokoke Forest Night Walk",
        "A guided night walk through Kenya's largest coastal forest "
        "to spot owls, galagos, and golden-rumped elephant shrews.",
        "Malindi",
        ["Nature", "Adventure"],
        34,
        0,
    ),
    (
        "Mount Longonot Day Hike",
        "A guided day hike up Mount Longonot's crater rim with " "panoramic Rift Valley views.",
        "Naivasha",
        ["Nature", "Adventure"],
        12,
        0,
    ),
    (
        "Watamu Marine Park Snorkelling",
        "Guided snorkelling excursion in Watamu Marine National Park " "to explore coral gardens and tropical fish.",
        "Malindi",
        ["Nature"],
        46,
        0,
    ),
    (
        "Scottish Highlands Wildlife Safari",
        "A 3-day guided wildlife safari in the Cairngorms searching " "for red deer, golden eagles, and red squirrels.",
        "Edinburgh",
        ["Nature"],
        170,
        3,
    ),
    (
        "London Wetland Centre Bird Walk",
        "An early-morning birding walk at the London Wetland Centre " "with an RSPB guide.",
        "London",
        ["Nature"],
        42,
        0,
    ),
    (
        "LA Griffith Park Sunset Hike",
        "A guided sunset hike in Griffith Park with views of the " "Hollywood Sign and downtown LA skyline.",
        "Los Angeles",
        ["Nature"],
        63,
        0,
    ),
    # ── Extra events to hit 80+ (past events ~10%) ──────────────────
    (
        "Nairobi Wine & Cheese Evening",
        "An evening of wine and artisan cheese pairings at a " "Westlands rooftop bar.",
        "Nairobi",
        ["Food & Drink"],
        -10,
        0,
    ),
    (
        "Mombasa Old Town Photography Walk",
        "A guided photography walk through Mombasa's historic " "Old Town capturing Swahili architecture.",
        "Mombasa",
        ["Culture", "Learning"],
        -20,
        0,
    ),
    (
        "Nairobi Half Marathon",
        "The annual Nairobi Half Marathon through Uhuru Gardens " "and the city centre.",
        "Nairobi",
        ["Sports"],
        -15,
        0,
    ),
    (
        "Lamu Yoga Retreat",
        "A 5-day yoga and wellness retreat on Shela Beach with " "daily classes, meditation, and healthy meals.",
        "Lamu",
        ["Learning", "Nature"],
        -5,
        5,
    ),
    (
        "Kisumu Sunset Dhow Cruise",
        "A sunset cruise on Lake Victoria aboard a traditional " "dhow with live taarab music.",
        "Kisumu",
        ["Travel", "Music & Events"],
        -25,
        0,
    ),
    (
        "London Afrobeats Brunch",
        "Brunch party featuring Afrobeats DJs, Nigerian jollof, " "and bottomless cocktails in Shoreditch.",
        "London",
        ["Music & Events", "Food & Drink"],
        -8,
        0,
    ),
    (
        "Manchester Craft Beer Festival",
        "Over 100 craft beers from independent UK breweries with " "street food and live music.",
        "Manchester",
        ["Food & Drink", "Music & Events"],
        -12,
        2,
    ),
    (
        "NYC African Diaspora Book Fair",
        "A book fair celebrating African and Caribbean authors with " "readings, signings, and panel discussions.",
        "New York",
        ["Culture", "Learning"],
        -18,
        2,
    ),
    # ── Additional events to exceed 80 ──────────────────────────────
    (
        "Nairobi Whisky & Cigar Lounge Night",
        "An evening of premium whisky tastings and cigar pairings " "at a Westlands speakeasy.",
        "Nairobi",
        ["Food & Drink"],
        112,
        0,
    ),
    (
        "Mombasa Kite Festival",
        "Hundreds of colourful kites fill the sky above Nyali " "Beach in this family-friendly annual festival.",
        "Mombasa",
        ["Culture", "Nature"],
        56,
        2,
    ),
    (
        "Nakuru Cycling Challenge",
        "A 100 km cycling challenge around Lake Nakuru with scenic " "views and wildlife sightings.",
        "Nakuru",
        ["Sports", "Adventure"],
        43,
        0,
    ),
    (
        "Nairobi Pottery Workshop",
        "Hands-on pottery classes at the Kazuri Beads factory " "learning traditional Kenyan ceramic techniques.",
        "Nairobi",
        ["Learning", "Culture"],
        22,
        0,
    ),
    (
        "Diani Deep Sea Fishing Tournament",
        "Annual deep-sea fishing competition off the Diani coast " "targeting marlin, sailfish, and yellowfin tuna.",
        "Diani",
        ["Sports", "Nature"],
        102,
        2,
    ),
    (
        "Birmingham Reggae Marathon",
        "A full marathon through Birmingham with reggae sound " "systems at every mile cheering runners on.",
        "Birmingham",
        ["Sports", "Music & Events"],
        142,
        0,
    ),
    (
        "London Kenyan Food Pop-Up",
        "A pop-up restaurant in Peckham serving nyama choma, " "ugali, and Kenyan street food favourites.",
        "London",
        ["Food & Drink", "Culture"],
        77,
        3,
    ),
    (
        "LA Outdoor Film Screening",
        "Classic films screened under the stars at the Hollywood " "Forever Cemetery with food trucks.",
        "Los Angeles",
        ["Culture", "Music & Events"],
        88,
        0,
    ),
    (
        "Nairobi Green City Marathon",
        "An eco-themed marathon promoting urban greening with " "tree planting along the route.",
        "Nairobi",
        ["Sports", "Nature"],
        -7,
        0,
    ),
    (
        "Malindi Sea Turtle Release",
        "Help release rehabilitated sea turtles back into the " "Indian Ocean with marine conservationists.",
        "Malindi",
        ["Nature", "Learning"],
        33,
        0,
    ),
]


class Command(BaseCommand):
    help = "Seed the database with 80+ events across all categories"

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete all existing events before seeding",
        )

    def handle(self, *args, **options):
        if options["flush"]:
            count, _ = Event.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {count} existing events."))

        # Load categories created by load_initial_data
        categories = {}
        for cat in Category.objects.all():
            categories[cat.name] = cat

        if not categories:
            self.stderr.write(self.style.ERROR("No categories found. Run load_initial_data first."))
            return

        created_count = 0
        skipped_count = 0

        for (
            name,
            description,
            city,
            cat_names,
            days_offset,
            duration_days,
        ) in EVENTS_DATA:
            start = _dt(days_offset)
            end = start + timedelta(days=duration_days) if duration_days else None  # noqa: E501
            primary_cat = cat_names[0] if cat_names else "Travel"

            event, created = Event.objects.get_or_create(
                name=name,
                defaults={
                    "description": description,
                    "date": start,
                    "end_date": end,
                    "location_name": city,
                    "location": COORDS.get(city),
                    "timezone": TIMEZONES.get(city, "Africa/Nairobi"),
                    "image": IMAGES.get(primary_cat, ""),
                    "is_active": True,
                },
            )

            if created:
                # Set M2M categories
                for cat_name in cat_names:
                    cat = categories.get(cat_name)
                    if cat:
                        event.category.add(cat)
                created_count += 1
            else:
                skipped_count += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded {created_count} events " f"({skipped_count} already existed)."))
