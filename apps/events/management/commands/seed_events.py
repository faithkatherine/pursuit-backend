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
    "Talks & Ideas": f"{_U}1524178232363-1fb2b075b655{_Q}",
    "Workshops & Classes": f"{_U}1524178232363-1fb2b075b655{_Q}",
    "Concerts & Nightlife": f"{_U}1459749411175-04bf5292ceea{_Q}",
    "Culture & Arts": f"{_U}1533669955142-6a73332af4db{_Q}",
    "Outdoors & Active": f"{_U}1533692328991-08159ff19fca{_Q}",
    "Food & Drink": f"{_U}1504674900247-0877df9cc836{_Q}",
    "Markets & Pop-ups": f"{_U}1533669955142-6a73332af4db{_Q}",
    "Travel": f"{_U}1488085061387-422e29b40080{_Q}",
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
        ["Travel", "Culture & Arts"],
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
        ["Travel", "Outdoors & Active"],
        90,
        3,
    ),
    (
        "Diani Beach Festival",
        "A week-long festival celebrating Diani's stunning beaches with "
        "kite-surfing demos, beach volleyball, and sundowner events.",
        "Diani",
        ["Travel", "Outdoors & Active"],
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
        ["Travel", "Culture & Arts"],
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
    # ── Outdoors & Active (5 Kenya, 2 UK, 1 US) ─────────────────────────────
    (
        "Mount Kenya Ultra Trail",
        "A grueling ultra-marathon around Mount Kenya through forests, " "moorlands, and high-altitude terrain.",
        "Nakuru",
        ["Outdoors & Active"],
        35,
        2,
    ),
    (
        "Hell's Gate Rock Climbing Weekend",
        "Guided rock climbing and gorge walking in Hell's Gate " "National Park near Lake Naivasha.",
        "Naivasha",
        ["Outdoors & Active"],
        20,
        2,
    ),
    (
        "Diani Skydiving Experience",
        "Tandem skydiving over the turquoise waters of the Indian Ocean " "at Diani Beach.",
        "Diani",
        ["Outdoors & Active"],
        50,
        0,
    ),
    (
        "Masai Mara Balloon Safari",
        "A sunrise hot air balloon ride over the Masai Mara with " "champagne bush breakfast.",
        "Nairobi",
        ["Outdoors & Active"],
        40,
        0,
    ),
    (
        "Tana River White Water Rafting",
        "Exciting white-water rafting on the Tana River with Class III " "and IV rapids near Sagana.",
        "Nairobi",
        ["Outdoors & Active"],
        25,
        0,
    ),
    (
        "Lake District Adventure Weekend",
        "Kayaking, fell running, and wild camping in England's Lake " "District National Park.",
        "Manchester",
        ["Outdoors & Active"],
        55,
        2,
    ),
    (
        "Scottish Highlands Survival Course",
        "A wilderness survival course in the Scottish Highlands covering " "fire-making, foraging, and navigation.",
        "Edinburgh",
        ["Outdoors & Active", "Workshops & Classes"],
        80,
        3,
    ),
    (
        "NYC Urban Adventure Race",
        "A city-wide adventure race through New York's boroughs " "combining running, cycling, and problem-solving.",
        "New York",
        ["Outdoors & Active"],
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
        ["Food & Drink", "Culture & Arts"],
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
        ["Food & Drink", "Culture & Arts"],
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
        ["Food & Drink", "Culture & Arts"],
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
    # ── Culture & Arts (5 Kenya, 2 UK, 1 US) ───────────────────────────────
    (
        "Nairobi Art Week",
        "A week of gallery openings, studio tours, and public art "
        "installations across Nairobi's creative districts.",
        "Nairobi",
        ["Culture & Arts"],
        22,
        7,
    ),
    (
        "Kisumu Suba Cultural Festival",
        "A celebration of the Suba people's traditions with dance, "
        "music, and storytelling on the shores of Lake Victoria.",
        "Kisumu",
        ["Culture & Arts"],
        48,
        2,
    ),
    (
        "Mombasa Swahili Heritage Walk",
        "Guided heritage walks through Mombasa Old Town exploring "
        "Fort Jesus, Swahili architecture, and local crafts.",
        "Mombasa",
        ["Culture & Arts", "Talks & Ideas"],
        18,
        0,
    ),
    (
        "Nakuru Blankets & Wine",
        "An outdoor picnic-style event featuring live bands, DJs, " "and local food vendors in Nakuru's Hyrax Hill.",
        "Nakuru",
        ["Culture & Arts", "Concerts & Nightlife"],
        32,
        0,
    ),
    (
        "Kenya Fashion Week",
        "Showcasing African fashion designers with runway shows, " "pop-up markets, and industry workshops.",
        "Nairobi",
        ["Culture & Arts", "Markets & Pop-ups"],
        105,
        4,
    ),
    (
        "London African Film Festival",
        "Screenings, panels, and Q&As celebrating the best of " "African cinema at BFI Southbank.",
        "London",
        ["Culture & Arts"],
        140,
        10,
    ),
    (
        "Manchester International Festival",
        "A biennial festival of original new work from across the " "arts including theatre, music, and visual art.",
        "Manchester",
        ["Culture & Arts", "Concerts & Nightlife"],
        160,
        18,
    ),
    (
        "Harlem Cultural Festival NYC",
        "Celebrating Harlem's rich cultural heritage with live " "performances, art exhibits, and soul food.",
        "New York",
        ["Culture & Arts", "Concerts & Nightlife"],
        115,
        2,
    ),
    # ── Workshops & Classes / Talks & Ideas (5 Kenya, 2 UK, 1 US) ──────────────────────────────
    (
        "Nairobi Tech Week",
        "East Africa's largest tech conference with workshops on AI, " "fintech, and mobile innovation.",
        "Nairobi",
        ["Workshops & Classes", "Talks & Ideas"],
        28,
        5,
    ),
    (
        "Swahili Language Immersion Lamu",
        "A week-long Swahili language course on Lamu Island combining " "classroom learning with cultural immersion.",
        "Lamu",
        ["Workshops & Classes", "Culture & Arts"],
        60,
        7,
    ),
    (
        "Wildlife Photography Masterclass",
        "A hands-on photography workshop in Nakuru National Park led " "by award-winning wildlife photographers.",
        "Nakuru",
        ["Workshops & Classes", "Outdoors & Active"],
        38,
        3,
    ),
    (
        "Kisumu Entrepreneurship Bootcamp",
        "An intensive bootcamp for aspiring entrepreneurs covering "
        "business planning, funding, and digital marketing.",
        "Kisumu",
        ["Workshops & Classes"],
        72,
        5,
    ),
    (
        "Mombasa Marine Biology Workshop",
        "Learn about coral reef conservation and marine ecosystems " "at the Kenya Marine Research Institute.",
        "Mombasa",
        ["Workshops & Classes", "Outdoors & Active"],
        88,
        3,
    ),
    (
        "Oxford Creative Writing Retreat",
        "A weekend writing retreat at an Oxford college with sessions " "on fiction, poetry, and memoir.",
        "London",
        ["Workshops & Classes"],
        125,
        2,
    ),
    (
        "Edinburgh Science Festival",
        "Hands-on science workshops, talks, and exhibitions for " "curious minds of all ages.",
        "Edinburgh",
        ["Workshops & Classes", "Talks & Ideas"],
        145,
        14,
    ),
    (
        "Atlanta Startup Summit",
        "Workshops and mentoring sessions connecting founders with " "investors and industry leaders.",
        "Atlanta",
        ["Workshops & Classes", "Talks & Ideas"],
        98,
        2,
    ),
    # ── Outdoors & Active - Sports (5 Kenya, 2 UK, 1 US) ────────────────────────────────
    (
        "Nairobi Marathon",
        "The annual Nairobi Marathon attracting elite runners and " "amateurs through the city's scenic routes.",
        "Nairobi",
        ["Outdoors & Active"],
        44,
        0,
    ),
    (
        "Diani Beach Triathlon",
        "Swim, cycle, and run along the stunning Diani coastline " "in this popular multi-sport event.",
        "Diani",
        ["Outdoors & Active"],
        58,
        0,
    ),
    (
        "Kenya Sevens Rugby Festival",
        "The electrifying Kenya Sevens rugby tournament with live " "music, food, and family entertainment.",
        "Nairobi",
        ["Outdoors & Active", "Concerts & Nightlife"],
        36,
        2,
    ),
    (
        "Lewa Safari Marathon",
        "Run a marathon through a wildlife conservancy alongside " "giraffes, zebras, and elephants.",
        "Nairobi",
        ["Outdoors & Active"],
        82,
        0,
    ),
    (
        "Kisumu Boat Race",
        "Annual boat racing on Lake Victoria with rowing, sailing, " "and traditional dhow competitions.",
        "Kisumu",
        ["Outdoors & Active"],
        68,
        0,
    ),
    (
        "London Marathon Expo",
        "The official expo for the London Marathon with gear, " "nutrition, and running workshops.",
        "London",
        ["Outdoors & Active"],
        135,
        3,
    ),
    (
        "Manchester City Football Experience",
        "Behind-the-scenes stadium tours, coaching clinics, and " "match-day experiences at the Etihad.",
        "Manchester",
        ["Outdoors & Active"],
        52,
        0,
    ),
    (
        "NYC Basketball Classic",
        "An outdoor basketball tournament in Harlem featuring " "streetball legends and rising stars.",
        "New York",
        ["Outdoors & Active"],
        78,
        2,
    ),
    # ── Concerts & Nightlife (5 Kenya, 2 UK, 1 US) ────────────────────────
    (
        "Koroga Festival Nairobi",
        "Kenya's favourite outdoor music festival blending Afrobeats, " "jazz, and soul with gourmet food trucks.",
        "Nairobi",
        ["Concerts & Nightlife"],
        26,
        0,
    ),
    (
        "Sauti za Busara Mombasa Satellite",
        "A satellite edition of the Sauti za Busara music festival " "bringing East African sounds to the coast.",
        "Mombasa",
        ["Concerts & Nightlife", "Culture & Arts"],
        62,
        3,
    ),
    (
        "Nakuru Jazz & Blues Night",
        "A monthly jazz and blues night featuring Kenyan and " "international musicians at Nakuru's Lake Basin.",
        "Nakuru",
        ["Concerts & Nightlife"],
        14,
        0,
    ),
    (
        "Malindi Beach Music Festival",
        "A beachside music festival with reggae, Afro-pop, and " "Taarab performances under the stars.",
        "Malindi",
        ["Concerts & Nightlife"],
        92,
        2,
    ),
    (
        "Nairobi Acoustic Sessions",
        "Intimate acoustic performances by Kenyan singer-songwriters " "at Nairobi's rooftop venues.",
        "Nairobi",
        ["Concerts & Nightlife"],
        10,
        0,
    ),
    (
        "Notting Hill Carnival Warm-Up",
        "Pre-carnival live music, steel pan workshops, and Caribbean " "food in West London.",
        "London",
        ["Concerts & Nightlife", "Culture & Arts"],
        155,
        2,
    ),
    (
        "Edinburgh Hogmanay Concert",
        "New Year's Eve concert and fireworks celebration in " "Edinburgh's Princes Street Gardens.",
        "Edinburgh",
        ["Concerts & Nightlife"],
        180,
        0,
    ),
    (
        "Atlanta Jazz Festival",
        "One of the largest free jazz festivals in the US, held " "annually in Piedmont Park.",
        "Atlanta",
        ["Concerts & Nightlife"],
        108,
        3,
    ),
    # ── Outdoors & Active - Nature (5 Kenya, 2 UK, 1 US) ────────────────────────────────
    (
        "Great Wildebeest Migration Viewing",
        "Guided safari viewing of the Great Migration at the Masai " "Mara with expert naturalist guides.",
        "Nairobi",
        ["Outdoors & Active"],
        50,
        3,
    ),
    (
        "Lake Nakuru Flamingo Walk",
        "A guided birding walk to see the famous flamingos and " "pelicans of Lake Nakuru National Park.",
        "Nakuru",
        ["Outdoors & Active"],
        16,
        0,
    ),
    (
        "Arabuko-Sokoke Forest Night Walk",
        "A guided night walk through Kenya's largest coastal forest "
        "to spot owls, galagos, and golden-rumped elephant shrews.",
        "Malindi",
        ["Outdoors & Active"],
        34,
        0,
    ),
    (
        "Mount Longonot Day Hike",
        "A guided day hike up Mount Longonot's crater rim with " "panoramic Rift Valley views.",
        "Naivasha",
        ["Outdoors & Active"],
        12,
        0,
    ),
    (
        "Watamu Marine Park Snorkelling",
        "Guided snorkelling excursion in Watamu Marine National Park " "to explore coral gardens and tropical fish.",
        "Malindi",
        ["Outdoors & Active"],
        46,
        0,
    ),
    (
        "Scottish Highlands Wildlife Safari",
        "A 3-day guided wildlife safari in the Cairngorms searching " "for red deer, golden eagles, and red squirrels.",
        "Edinburgh",
        ["Outdoors & Active"],
        170,
        3,
    ),
    (
        "London Wetland Centre Bird Walk",
        "An early-morning birding walk at the London Wetland Centre " "with an RSPB guide.",
        "London",
        ["Outdoors & Active"],
        42,
        0,
    ),
    (
        "LA Griffith Park Sunset Hike",
        "A guided sunset hike in Griffith Park with views of the " "Hollywood Sign and downtown LA skyline.",
        "Los Angeles",
        ["Outdoors & Active"],
        63,
        0,
    ),
    # ── New category examples + extras (~10%) ──────────────────────────────
    (
        "Achille Mbembe: Memory & Place",
        "The renowned philosopher speaks on memory, place, and " "belonging at Goethe-Institut Nairobi.",
        "Nairobi",
        ["Talks & Ideas"],
        52,
        0,
    ),
    (
        "Indigo Dyeing with Sosiani",
        "Hands-on indigo dyeing workshop with sustainable textile " "collective Sosiani in Nairobi.",
        "Nairobi",
        ["Workshops & Classes"],
        46,
        0,
    ),
    (
        "Spring Valley Farmers Market",
        "Weekly farmers market in Spring Valley with fresh produce, " "artisan breads, and local honey.",
        "Nairobi",
        ["Markets & Pop-ups", "Food & Drink"],
        7,
        0,
    ),
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
        ["Culture & Arts", "Workshops & Classes"],
        -20,
        0,
    ),
    (
        "Nairobi Half Marathon",
        "The annual Nairobi Half Marathon through Uhuru Gardens " "and the city centre.",
        "Nairobi",
        ["Outdoors & Active"],
        -15,
        0,
    ),
    (
        "Lamu Yoga Retreat",
        "A 5-day yoga and wellness retreat on Shela Beach with " "daily classes, meditation, and healthy meals.",
        "Lamu",
        ["Workshops & Classes", "Outdoors & Active"],
        -5,
        5,
    ),
    (
        "Kisumu Sunset Dhow Cruise",
        "A sunset cruise on Lake Victoria aboard a traditional " "dhow with live taarab music.",
        "Kisumu",
        ["Travel", "Concerts & Nightlife"],
        -25,
        0,
    ),
    (
        "London Afrobeats Brunch",
        "Brunch party featuring Afrobeats DJs, Nigerian jollof, " "and bottomless cocktails in Shoreditch.",
        "London",
        ["Concerts & Nightlife", "Food & Drink"],
        -8,
        0,
    ),
    (
        "Manchester Craft Beer Festival",
        "Over 100 craft beers from independent UK breweries with " "street food and live music.",
        "Manchester",
        ["Food & Drink", "Concerts & Nightlife"],
        -12,
        2,
    ),
    (
        "NYC African Diaspora Book Fair",
        "A book fair celebrating African and Caribbean authors with " "readings, signings, and panel discussions.",
        "New York",
        ["Culture & Arts", "Talks & Ideas"],
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
        ["Culture & Arts", "Outdoors & Active"],
        56,
        2,
    ),
    (
        "Nakuru Cycling Challenge",
        "A 100 km cycling challenge around Lake Nakuru with scenic " "views and wildlife sightings.",
        "Nakuru",
        ["Outdoors & Active"],
        43,
        0,
    ),
    (
        "Nairobi Pottery Workshop",
        "Hands-on pottery classes at the Kazuri Beads factory " "learning traditional Kenyan ceramic techniques.",
        "Nairobi",
        ["Workshops & Classes", "Culture & Arts"],
        22,
        0,
    ),
    (
        "Diani Deep Sea Fishing Tournament",
        "Annual deep-sea fishing competition off the Diani coast " "targeting marlin, sailfish, and yellowfin tuna.",
        "Diani",
        ["Outdoors & Active"],
        102,
        2,
    ),
    (
        "Birmingham Reggae Marathon",
        "A full marathon through Birmingham with reggae sound " "systems at every mile cheering runners on.",
        "Birmingham",
        ["Outdoors & Active", "Concerts & Nightlife"],
        142,
        0,
    ),
    (
        "London Kenyan Food Pop-Up",
        "A pop-up restaurant in Peckham serving nyama choma, " "ugali, and Kenyan street food favourites.",
        "London",
        ["Food & Drink", "Markets & Pop-ups"],
        77,
        3,
    ),
    (
        "LA Outdoor Film Screening",
        "Classic films screened under the stars at the Hollywood " "Forever Cemetery with food trucks.",
        "Los Angeles",
        ["Culture & Arts", "Concerts & Nightlife"],
        88,
        0,
    ),
    (
        "Nairobi Green City Marathon",
        "An eco-themed marathon promoting urban greening with " "tree planting along the route.",
        "Nairobi",
        ["Outdoors & Active"],
        -7,
        0,
    ),
    (
        "Malindi Sea Turtle Release",
        "Help release rehabilitated sea turtles back into the " "Indian Ocean with marine conservationists.",
        "Malindi",
        ["Outdoors & Active", "Workshops & Classes"],
        33,
        0,
    ),
]


# Curator notes moved to EditorsPick model — no longer stored on Event
CURATOR_NOTES = {}

# Near-term events for "Next Up" strip testing
# (name, description, city, categories, hours_from_now, curator_note, curator_name)
NEAR_TERM_EVENTS = [
    (
        "Westlands Rooftop Sundowner",
        "Sunset cocktails and live acoustic sets at a Westlands rooftop bar.",
        "Nairobi",
        ["Food & Drink", "Concerts & Nightlife"],
        8,
        "The best sunset view in town \u2014 grab the corner table",
        "Joy, Pursuit Food Editor",
    ),
    (
        "Karen Night Market",
        "Artisan vendors, street food, and live music at the Karen Hub.",
        "Nairobi",
        ["Food & Drink", "Markets & Pop-ups"],
        14,
        None,
        None,
    ),
    (
        "Uhuru Gardens Yoga at Dawn",
        "A free community yoga session at sunrise in Uhuru Gardens.",
        "Nairobi",
        ["Outdoors & Active"],
        20,
        None,
        None,
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
        parser.add_argument(
            "--scenario",
            choices=["a", "b"],
            default="a",
            help="Scenario A = no trip; Scenario B = trip + events",
        )

    def handle(self, *args, **options):
        from apps.events.models import UserEvents
        from apps.itinerary.models import Trip
        from django.contrib.auth import get_user_model

        User = get_user_model()

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

        # --- Seed base events ---
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
                for cat_name in cat_names:
                    cat = categories.get(cat_name)
                    if cat:
                        event.category.add(cat)
                created_count += 1
            else:
                skipped_count += 1

        # --- Seed near-term events ---
        near_term_count = 0
        for (
            name,
            description,
            city,
            cat_names,
            hours_from_now,
            _curator_note,  # Ignored - curator notes now in EditorsPick
            _curator_name,
        ) in NEAR_TERM_EVENTS:
            start = timezone.now() + timedelta(hours=hours_from_now)
            primary_cat = cat_names[0] if cat_names else "Food & Drink"

            event, created = Event.objects.get_or_create(
                name=name,
                defaults={
                    "description": description,
                    "date": start,
                    "end_date": None,
                    "location_name": city,
                    "location": COORDS.get(city),
                    "timezone": TIMEZONES.get(city, "Africa/Nairobi"),
                    "image": IMAGES.get(primary_cat, ""),
                    "is_active": True,
                },
            )
            if created:
                for cat_name in cat_names:
                    cat = categories.get(cat_name)
                    if cat:
                        event.category.add(cat)
                near_term_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {created_count} events ({skipped_count} already existed), "
            f"{near_term_count} near-term events."
        ))

        # --- Seed Editor's Picks ---
        from apps.events.models import EditorsPick

        picks_data = [
            # Nairobi - active now
            ("Wildlife Photography Masterclass", "nairobi", 0, 14,
             "Nakuru National Park offers some of East Africa\u2019s most stunning wildlife backdrops \u2014 this workshop is a rare chance to learn from award-winning pros who know every corner of the park. Perfect for serious hobbyists and aspiring pros alike.",
             "Amani, Pursuit Editor"),
            # Mombasa - active now
            ("Mombasa Street Food Festival", "mombasa", 0, 14,
             "The coastal street food scene is unlike anywhere else in Kenya \u2014 come hungry and expect biryani that rivals Zanzibar\u2019s best. The viazi karai alone is worth the trip.",
             "Joy, Pursuit Food Editor"),
            # Kisumu - active in 2 weeks
            ("Kisumu Fish Festival", "kisumu", 14, 21,
             "Lake Victoria\u2019s fishing heritage comes alive in this two-day lakeside celebration. Don\u2019t miss the omena tastings \u2014 crispy, fresh, and served with ugali on the shore.",
             "Kofi, Pursuit Culture Editor"),
        ]

        picks_created = 0
        picks_skipped = 0

        for event_name, location_tag, active_from_days, active_until_days, curator_note, curator_name in picks_data:
            event = Event.objects.filter(name=event_name).first()
            if not event:
                self.stdout.write(self.style.WARNING(f"Event '{event_name}' not found for Editor's Pick — skipping."))
                continue

            active_from = timezone.now() + timedelta(days=active_from_days)
            active_until = timezone.now() + timedelta(days=active_until_days)

            pick, created = EditorsPick.objects.get_or_create(
                event=event,
                location_tag=location_tag,
                defaults={
                    "active_from": active_from,
                    "active_until": active_until,
                    "curator_note": curator_note,
                    "curator_name": curator_name,
                    "position": 1,
                }
            )

            if created:
                picks_created += 1
            else:
                # Update if exists
                pick.active_from = active_from
                pick.active_until = active_until
                pick.curator_note = curator_note
                pick.curator_name = curator_name
                pick.save(update_fields=["active_from", "active_until", "curator_note", "curator_name"])
                picks_skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {picks_created} Editor's Picks ({picks_skipped} already existed)."
        ))

        # --- Scenario setup for test user ---
        test_user = User.objects.filter(email="faithcathy12@gmail.com").first()
        if not test_user:
            self.stdout.write(self.style.WARNING("Test user not found — skipping scenario setup."))
            return

        scenario = options["scenario"]

        # Save near-term events for the test user (so "Next Up" works)
        for name, *_ in NEAR_TERM_EVENTS:
            event = Event.objects.filter(name=name).first()
            if event:
                UserEvents.objects.get_or_create(user=test_user, event=event)

        if scenario == "b":
            # Create a trip within 30 days
            trip_start = timezone.now() + timedelta(days=5)
            trip_end = trip_start + timedelta(days=4)
            trip, trip_created = Trip.objects.get_or_create(
                user=test_user,
                name="Nairobi Adventure",
                defaults={
                    "destination": "Nairobi",
                    "start_date": trip_start,
                    "end_date": trip_end,
                    "cover_image": IMAGES.get("Travel", ""),
                },
            )
            if trip_created:
                self.stdout.write(self.style.SUCCESS("Created trip: Nairobi Adventure"))
            else:
                # Ensure dates are within 30 days
                trip.start_date = trip_start
                trip.end_date = trip_end
                trip.save(update_fields=["start_date", "end_date"])
                self.stdout.write(self.style.SUCCESS("Updated trip dates: Nairobi Adventure"))
        elif scenario == "a":
            # Remove any trips within 30 days
            now = timezone.now()
            thirty_days = now + timedelta(days=30)
            removed = Trip.objects.filter(
                user=test_user,
                end_date__gte=now,
                start_date__lte=thirty_days,
            ).update(start_date=now + timedelta(days=60), end_date=now + timedelta(days=65))
            if removed:
                self.stdout.write(self.style.WARNING(f"Moved {removed} trip(s) out of 30-day window for scenario A."))

        self.stdout.write(self.style.SUCCESS(f"Scenario {scenario.upper()} configured for test user."))
