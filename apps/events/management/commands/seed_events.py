import os
import re
from decimal import Decimal
from datetime import timedelta

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.models import Category
from apps.events.models import EditorsPick, Event
from apps.events.utils.unsplash import (
    FALLBACK_IMAGE_URLS,
    fetch_unsplash_gallery_images,
    fetch_unsplash_image_url,
)

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


CATEGORY_NAMES_BY_SLUG = {
    "concerts-and-nightlife": "Concerts & Nightlife",
    "outdoors-and-active": "Outdoors & Active",
    "food-and-drink": "Food & Drink",
    "culture-and-arts": "Culture & Arts",
    "talks-and-ideas": "Talks & Ideas",
    "workshops-and-classes": "Workshops & Classes",
    "markets-and-popups": "Markets & Pop-ups",
    "travel": "Travel",
}

VENUES = {
    "Alchemist Bar": {"neighborhood": "Westlands", "point": Point(36.8047, -1.2640, srid=4326)},
    "GoDown Arts Centre": {"neighborhood": "Ngara", "point": Point(36.8393, -1.2913, srid=4326)},
    "Karura Forest": {"neighborhood": "Gigiri", "point": Point(36.8391, -1.2341, srid=4326)},
    "Alliance Française": {"neighborhood": "Westlands", "point": Point(36.8065, -1.2648, srid=4326)},
    "Circle Art Gallery": {"neighborhood": "Lavington", "point": Point(36.7793, -1.2898, srid=4326)},
    "Spring Valley Community Market": {"neighborhood": "Spring Valley", "point": Point(36.7930, -1.2534, srid=4326)},
    "Ngong Racecourse": {"neighborhood": "Ngong Rd", "point": Point(36.7560, -1.3158, srid=4326)},
    "PAWA254": {"neighborhood": "Nairobi West", "point": Point(36.8202, -1.3065, srid=4326)},
    "Cultiva Farm": {"neighborhood": "Tigoni", "point": Point(36.6667, -1.1333, srid=4326)},
    "Nairobi National Museum": {"neighborhood": "CBD", "point": Point(36.8157, -1.2734, srid=4326)},
    "The Hub Karen": {"neighborhood": "Karen", "point": Point(36.7073, -1.3194, srid=4326)},
}

EXTERNAL_LINKS = {
    "Alchemist Bar": "https://alchemistbar.co.ke/events",
    "Alliance Française": "https://www.alliance-francaise.or.ke",
    "GoDown Arts Centre": "https://www.godown.or.ke",
}


def _next_weekday_start(weekday, hour):
    now = timezone.localtime(timezone.now())
    days_ahead = (weekday - now.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return now.replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=days_ahead)


def _generated_start(schedule):
    kind, amount, hour = schedule
    now = timezone.localtime(timezone.now())
    if kind == "hours":
        return now + timedelta(hours=amount)
    if kind == "weekend":
        return _next_weekday_start(amount, hour)
    return now.replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=amount)


GENERATED_NAIROBI_EVENTS = [
    {
        "name": "Jazz & Spoken Word at Alchemist",
        "category_slug": "concerts-and-nightlife",
        "venue": "Alchemist Bar",
        "schedule": ("hours", 2, None),
        "duration_days": 0,
        "is_free": False,
        "ticketing_enabled": False,
        "curator_note": "Get the courtyard seats - the indoor sound is muddier after 10pm. Arrive before the first poetry set if you want a clean view of the band.",
        "curator_name": "Pursuit team",
        "description": "A late-night blend of Nairobi jazz players and spoken word poets takes over the Alchemist courtyard. The KES 1,500 ticket is worth it for the rotating house band and the easy shift from poems to dancefloor. Dress light and carry ID because entry is 18+ and parking along Parklands Road fills fast. The outdoor courtyard fills up by 9pm - arrive early for the good spots near the stage.",
    },
    {
        "name": "Karura Twilight Trail Run",
        "category_slug": "outdoors-and-active",
        "venue": "Karura Forest",
        "schedule": ("hours", 4, None),
        "duration_days": 0,
        "is_free": False,
        "ticketing_enabled": True,
        "curator_note": "Carry a headlamp even if the route starts before sunset. The final forest section gets dark faster than most first-timers expect.",
        "curator_name": "Kamau, Pursuit",
        "description": "A guided 8K twilight loop winds through Karura Forest from the Limuru Road side. The KES 800 entry keeps the group small, with pacers for social runners and a quick stretch circle after the finish. Bring trail shoes, a headlamp, and your own water bottle because the kiosks close early. The marshland path gets slippery after afternoon rain, so do not wear brand-new road shoes.",
    },
    {
        "name": "Spring Valley Street Food Sundowner",
        "category_slug": "food-and-drink",
        "venue": "Spring Valley Community Market",
        "schedule": ("hours", 5, None),
        "duration_days": 0,
        "is_free": True,
        "ticketing_enabled": False,
        "curator_note": None,
        "curator_name": "Pursuit team",
        "description": "Spring Valley Community Market hosts a twilight food crawl with grills, coastal snacks, and small-batch drinks. Entry is free, which makes it a relaxed way to sample several Nairobi vendors without committing to one restaurant. Carry cash for the smaller stalls and a warm layer once the sun drops behind the tents. The best mshikaki queue is usually the quiet one tucked near the flower sellers.",
    },
    {
        "name": "Blankets & Wine June Picnic",
        "category_slug": "concerts-and-nightlife",
        "venue": "Ngong Racecourse",
        "schedule": ("weekend", 5, 14),
        "duration_days": 0,
        "is_free": False,
        "ticketing_enabled": True,
        "curator_note": "Set up slightly left of the sound desk for the best balance of stage view and space. The main gate queue moves slowly after 3pm.",
        "curator_name": "Pursuit team",
        "description": "Blankets & Wine returns to Ngong Racecourse with an outdoor lineup of Kenyan live acts and DJs. The KES 4,500 ticket buys a full afternoon-to-evening picnic rhythm rather than a rushed concert. Bring a kikapu, sunscreen, and a mat, but leave glass bottles at home because security checks are strict. The far food court lines are shorter than the ones nearest the main stage.",
    },
    {
        "name": "Circle Art Saturday Preview",
        "category_slug": "culture-and-arts",
        "venue": "Circle Art Gallery",
        "schedule": ("weekend", 5, 11),
        "duration_days": 0,
        "is_free": True,
        "ticketing_enabled": False,
        "curator_note": "Go in the first hour if you want quiet with the work. By noon the front room turns into a social stop-off.",
        "curator_name": "Pursuit team",
        "description": "Circle Art Gallery opens a Saturday preview of new painting and mixed-media work by East African artists. The free entry makes it easy to drop in, but the real draw is hearing gallery staff unpack the smaller pieces people often miss. Wear comfortable shoes and plan for street parking around Lavington. The back room usually has the strongest pieces even when the crowd gathers near the entrance.",
    },
    {
        "name": "Karen Makers Morning",
        "category_slug": "workshops-and-classes",
        "venue": "The Hub Karen",
        "schedule": ("weekend", 6, 10),
        "duration_days": 0,
        "is_free": False,
        "ticketing_enabled": True,
        "curator_note": None,
        "curator_name": "Pursuit team",
        "description": "A hands-on Sunday session at The Hub Karen pairs beginner pottery, textile stamping, and quick craft demos. The KES 2,200 ticket includes basic materials and enough guidance to leave with something finished. Wear clothes that can handle clay dust and arrive before the mall parking rush builds. The workshop tables near the garden side have the best natural light for photos.",
    },
    {
        "name": "Spring Valley Craft & Plant Market",
        "category_slug": "markets-and-popups",
        "venue": "Spring Valley Community Market",
        "schedule": ("weekend", 6, 12),
        "duration_days": 0,
        "is_free": True,
        "ticketing_enabled": False,
        "curator_note": None,
        "curator_name": "Pursuit team",
        "description": "Independent makers and plant vendors gather at Spring Valley Community Market for a slow Sunday browse. Entry is free and the stall mix leans practical, with ceramics, herbs, woven baskets, and kids' snacks. Carry a tote bag and small notes because several stalls still prefer cash for low-value purchases. The herb seedlings near the back sell out before lunch when the weather is good.",
    },
    {
        "name": "Alliance Française African Film Night",
        "category_slug": "talks-and-ideas",
        "venue": "Alliance Française",
        "schedule": ("days", 1, 19),
        "duration_days": 0,
        "is_free": False,
        "ticketing_enabled": False,
        "curator_note": "Sit closer than you think for the post-film Q&A. The courtyard chatter can swallow softer questions from the back rows.",
        "curator_name": "Pursuit team",
        "description": "Alliance Française hosts an evening screening followed by a conversation with Nairobi film programmers. The KES 1,000 ticket is good value because the Q&A often reveals the production stories behind the film. Carry a light jacket for the courtyard and check traffic into Westlands before leaving home. The cafe queue spikes right after credits, so order before the screening starts.",
    },
    {
        "name": "Clay Forms Workshop at GoDown",
        "category_slug": "workshops-and-classes",
        "venue": "GoDown Arts Centre",
        "schedule": ("days", 2, 18),
        "duration_days": 0,
        "is_free": False,
        "ticketing_enabled": False,
        "curator_note": None,
        "curator_name": "Pursuit team",
        "description": "GoDown Arts Centre runs a beginner clay workshop focused on small functional pieces and surface texture. The KES 3,000 fee covers materials, firing coordination, and a patient instructor who keeps the class moving. Wear sleeves you can roll up and avoid white shoes because the studio floor gets dusty. Ask for the corner table near the fan if Ngara is running warm that evening.",
    },
    {
        "name": "Karura Family Bird Walk",
        "category_slug": "outdoors-and-active",
        "venue": "Karura Forest",
        "schedule": ("days", 3, 7),
        "duration_days": 0,
        "is_free": False,
        "ticketing_enabled": True,
        "curator_note": None,
        "curator_name": "Pursuit team",
        "description": "A naturalist-led morning walk introduces families to Karura Forest's birds, trees, and quieter side trails. The KES 600 ticket keeps the pace gentle and includes a simple checklist for kids. Bring binoculars if you have them, closed shoes, and a snack for the waterfall stop. The early group usually sees more before cyclists and school groups arrive.",
    },
    {
        "name": "Creative Economies Talk at PAWA254",
        "category_slug": "talks-and-ideas",
        "venue": "PAWA254",
        "schedule": ("days", 4, 18),
        "duration_days": 0,
        "is_free": True,
        "ticketing_enabled": False,
        "curator_note": "Bring a notebook; the useful bits tend to come during audience questions, not the opening remarks.",
        "curator_name": "Kamau, Pursuit",
        "description": "PAWA254 hosts an open conversation on how Nairobi creatives price, publish, and protect their work. The free session is useful because it mixes photographers, writers, designers, and organizers in one room. Arrive early for a seat and expect a practical, phone-out note-taking crowd. The best networking usually happens outside by the stairs after the official close.",
    },
    {
        "name": "GoDown Open Studios Weekend",
        "category_slug": "culture-and-arts",
        "venue": "GoDown Arts Centre",
        "schedule": ("days", 15, 10),
        "duration_days": 2,
        "is_free": False,
        "ticketing_enabled": False,
        "curator_note": None,
        "curator_name": "Pursuit team",
        "description": "GoDown Arts Centre opens studio doors for a two-day look at works in progress, installations, and artist conversations. The KES 2,500 pass is strongest for people who like process as much as finished exhibitions. Wear comfortable shoes and give yourself enough time to move between studios without rushing. The quieter morning slots are when artists are most likely to talk through unfinished work.",
    },
    {
        "name": "Cultiva Farm Brunch Table",
        "category_slug": "food-and-drink",
        "venue": "Cultiva Farm",
        "schedule": ("days", 17, 11),
        "duration_days": 0,
        "is_free": False,
        "ticketing_enabled": True,
        "curator_note": "Book the earlier seating if you can. Tigoni mist clears slowly and the farm looks best before the afternoon crowd arrives.",
        "curator_name": "Pursuit team",
        "description": "Cultiva Farm hosts a long-table brunch built around seasonal produce, grilled plates, and slow Tigoni views. The KES 6,500 ticket is premium, but the farm setting and full menu make it feel like a proper day out. Carry a light sweater and plan your ride home before the second seating ends. The road in can be muddy after rain, so low cars should take it slowly.",
    },
    {
        "name": "Museum After Hours: Nairobi Then",
        "category_slug": "culture-and-arts",
        "venue": "Nairobi National Museum",
        "schedule": ("days", 20, 18),
        "duration_days": 0,
        "is_free": False,
        "ticketing_enabled": True,
        "curator_note": None,
        "curator_name": "Pursuit team",
        "description": "Nairobi National Museum opens after hours for guided rooms, archive stories, and a short courtyard performance. The KES 2,800 ticket works well for anyone who wants culture without a full-day museum plan. Bring a jacket and use the main museum parking rather than circling Museum Hill late. The guide near the railway photos usually has the sharpest Nairobi trivia.",
    },
    {
        "name": "Alchemist Vinyl Night Market",
        "category_slug": "markets-and-popups",
        "venue": "Alchemist Bar",
        "schedule": ("days", 23, 16),
        "duration_days": 0,
        "is_free": False,
        "ticketing_enabled": False,
        "curator_note": "Dig through the crates before sundown. The rare Kenyan pressings disappear before the DJs start pulling a crowd.",
        "curator_name": "Pursuit team",
        "description": "Alchemist Bar turns its courtyard into a vinyl, fashion, and zine pop-up with DJs threading the afternoon together. The KES 1,200 ticket fits the market-meets-night-out format and keeps the vendor lineup curated. Bring cash for records and check sleeves carefully before buying. The best secondhand jackets are usually on the rail closest to the pizza counter.",
    },
    {
        "name": "Nairobi to Coast Travel Clinic",
        "category_slug": "travel",
        "venue": "Nairobi National Museum",
        "schedule": ("days", 25, 14),
        "duration_days": 0,
        "is_free": False,
        "ticketing_enabled": True,
        "curator_note": "Useful if you are planning coast travel around real Nairobi schedules. Ask about the morning SGR buffer; it saves more trips than any packing hack.",
        "curator_name": "Pursuit team",
        "description": "Travel planners and coastal guides break down realistic Nairobi-to-Mombasa weekend routes, budgets, and stops. The KES 2,000 ticket is practical if you are trying to avoid vague advice and overpacked itineraries. Bring your calendar, route questions, and a sense of your budget before the planning clinic starts. The SGR timing tips are the part people end up photographing.",
    },
    {
        "name": "Ngong Racecourse Open-Air Afrobeats",
        "category_slug": "concerts-and-nightlife",
        "venue": "Ngong Racecourse",
        "schedule": ("days", 29, 17),
        "duration_days": 0,
        "is_free": False,
        "ticketing_enabled": True,
        "curator_note": None,
        "curator_name": "Pursuit team",
        "description": "A large outdoor Afrobeats bill brings Nairobi DJs and guest performers to Ngong Racecourse. The KES 8,000 VIP tier is for people who want shorter bar lines and a cleaner stage view. Dress for grass, carry ID, and plan a cab pickup away from the main gate. The sound is clearer from the middle lawn than from the food trucks.",
    },
    {
        "name": "Lavington Collectors Salon",
        "category_slug": "culture-and-arts",
        "venue": "Circle Art Gallery",
        "schedule": ("days", 32, 18),
        "duration_days": 0,
        "is_free": False,
        "ticketing_enabled": True,
        "curator_note": "Do not be shy about asking prices. The smaller works are where new collectors usually find the most interesting entry points.",
        "curator_name": "Pursuit team",
        "description": "Circle Art Gallery hosts an evening salon for new collectors, artists, and curators around contemporary East African work. The KES 3,500 ticket includes a guided walkthrough and a low-pressure introduction to buying art. Dress smart casual and arrive with questions rather than a fixed shopping list. The strongest conversations happen around the unframed works table.",
    },
    {
        "name": "Tigoni Weekend Escape Planning Lab",
        "category_slug": "travel",
        "venue": "Cultiva Farm",
        "schedule": ("days", 36, 10),
        "duration_days": 0,
        "is_free": False,
        "ticketing_enabled": True,
        "curator_note": None,
        "curator_name": "Pursuit team",
        "description": "Cultiva Farm hosts a small planning lab for quick Tigoni, Limuru, and tea-country weekend escapes. The KES 4,000 ticket includes brunch bites, route templates, and local operator recommendations. Bring a laptop or notebook and a realistic transport plan for your group. The back-road route suggestions are more useful than the obvious highway stops.",
    },
    {
        "name": "PAWA254 Podcast Sprint",
        "category_slug": "workshops-and-classes",
        "venue": "PAWA254",
        "schedule": ("days", 40, 9),
        "duration_days": 2,
        "is_free": False,
        "ticketing_enabled": True,
        "curator_note": None,
        "curator_name": "Pursuit team",
        "description": "PAWA254 runs a two-day podcast sprint covering format, recording, editing, and publishing basics. The KES 3,200 ticket is aimed at beginners who want to leave with a pilot segment, not just notes. Bring headphones, a charged laptop, and one episode idea you can test in class. The quietest recording corner is upstairs before the afternoon sessions begin.",
    },
]


NEW_NAIROBI_EVENTS = [
    {
        "name": "Jazz Mondays at Alchemist: Horns in the Courtyard",
        "category_slug": "concerts-and-nightlife",
        "venue": "Alchemist Bar",
        "schedule": ("days", 7, 20),
        "duration_days": 0,
        "price": Decimal("1200"),
        "ticketing_enabled": True,
        "available_tickets": 5,
        "going_count": 196,
        "series_name": "Jazz Mondays at Alchemist",
        "has_gallery": False,
        "description": "Alchemist Bar hosts a Monday jazz set built around horns, keys, and a rotating rhythm section. The KES 1,200 ticket keeps the room intimate and gives the band space to stretch beyond the usual covers. Carry ID, dress for the outdoor courtyard, and avoid driving if you plan to stay for the late DJ handover. The best sound is just behind the first row of planters, not right against the stage.",
    },
    {
        "name": "Jazz Mondays at Alchemist: Nairobi Standards",
        "category_slug": "concerts-and-nightlife",
        "venue": "Alchemist Bar",
        "schedule": ("days", 14, 20),
        "duration_days": 0,
        "price": Decimal("1500"),
        "ticketing_enabled": False,
        "available_tickets": None,
        "going_count": 214,
        "series_name": "Jazz Mondays at Alchemist",
        "has_gallery": False,
        "description": "The second Jazz Mondays session at Alchemist leans into Nairobi standards, soul, and loose late-night improvisation. The KES 1,500 cover is worth it if you like sets that feel different by the final chorus. Book a cab, bring a jacket, and use the external event link for door details. The courtyard fills after nearby office dinners, so the sweet spot is arriving just before 8pm.",
    },
    {
        "name": "Blankets & Wine Sunset Edition",
        "category_slug": "concerts-and-nightlife",
        "venue": "Ngong Racecourse",
        "schedule": ("days", 34, 15),
        "duration_days": 0,
        "price": Decimal("5500"),
        "ticketing_enabled": True,
        "available_tickets": 120,
        "going_count": 438,
        "series_name": "Blankets & Wine",
        "has_gallery": True,
        "gallery_description": "A photo set from past picnic concerts and open-air performances. Includes crowd blankets, stage moments, food vendors, and golden-hour views across the racecourse.",
        "description": "Blankets & Wine brings a sunset-leaning outdoor edition to Ngong Racecourse with live bands and guest DJs. The KES 5,500 ticket is premium, but the setting works for a full picnic afternoon that rolls into night. Bring a mat, sunscreen, and a warm layer because the field cools quickly after sundown. The easiest exit is usually through the less crowded gate near the food vendors.",
    },
    {
        "name": "Karura Forest Dawn Photography Walk",
        "category_slug": "outdoors-and-active",
        "venue": "Karura Forest",
        "schedule": ("hours", 3, None),
        "duration_days": 0,
        "price": Decimal("900"),
        "ticketing_enabled": True,
        "available_tickets": 35,
        "going_count": 74,
        "has_gallery": False,
        "description": "A guided dawn walk through Karura Forest focuses on light, texture, birds, and quiet landscape photography. The KES 900 ticket is friendly for beginners and includes route guidance from a photographer who knows the forest gates well. Bring a charged phone or camera, closed shoes, and a flask because the cafes are not open at the start. The early mist near the caves disappears fast once the sun clears the trees.",
    },
    {
        "name": "Cultiva Smokehouse Long Lunch",
        "category_slug": "food-and-drink",
        "venue": "Cultiva Farm",
        "schedule": ("weekend", 5, 13),
        "duration_days": 0,
        "price": Decimal("6500"),
        "ticketing_enabled": True,
        "available_tickets": 42,
        "going_count": 156,
        "has_gallery": False,
        "description": "Cultiva Farm hosts a smokehouse-style long lunch built around seasonal produce and slow-cooked plates. The KES 6,500 ticket is premium, but it feels like a countryside reset without leaving the Nairobi orbit. Carry a sweater, plan transport back from Tigoni, and wear shoes that can handle a farm path. The earlier seating gets the better valley light and a calmer kitchen rhythm.",
    },
    {
        "name": "Spring Valley Breakfast Market",
        "category_slug": "food-and-drink",
        "venue": "Spring Valley Community Market",
        "schedule": ("weekend", 6, 9),
        "duration_days": 0,
        "price": Decimal("0"),
        "ticketing_enabled": False,
        "available_tickets": None,
        "going_count": 129,
        "has_gallery": False,
        "description": "Spring Valley Community Market starts early with breakfast plates, bakery stalls, coffee, and fresh produce. Free entry makes it an easy Sunday plan for families and anyone doing a proper pantry run. Carry a tote and small notes because the best stalls move quickly. The mandazi tray near the coffee stand is usually gone before 10:30am.",
    },
    {
        "name": "Circle Art Night Viewing",
        "category_slug": "culture-and-arts",
        "venue": "Circle Art Gallery",
        "schedule": ("days", 9, 18),
        "duration_days": 0,
        "price": Decimal("2500"),
        "ticketing_enabled": True,
        "available_tickets": 0,
        "going_count": 88,
        "has_gallery": True,
        "gallery_description": "A gallery set showing installation details, wall texts, and opening-night moments. Includes close-ups of works and the Lavington gallery rooms after dark.",
        "description": "Circle Art Gallery opens for an evening viewing of contemporary painting, sculpture, and works on paper. The KES 2,500 ticket is aimed at people who want a slower walkthrough with curatorial context. Dress smart casual and plan for limited street parking in Lavington. The smaller works near the office corridor often reward a second pass.",
    },
    {
        "name": "Museum Courtyard History Salon",
        "category_slug": "talks-and-ideas",
        "venue": "Nairobi National Museum",
        "schedule": ("days", 4, 18),
        "duration_days": 0,
        "price": Decimal("0"),
        "ticketing_enabled": False,
        "available_tickets": None,
        "going_count": 67,
        "has_gallery": False,
        "description": "Nairobi National Museum hosts a courtyard salon on city memory, architecture, and old photographs. Free entry makes it a smart after-work stop for anyone curious about how Nairobi keeps changing. Bring a notebook and use the main museum parking before the evening traffic thickens. The best questions usually come from older attendees who remember the buildings being discussed.",
    },
    {
        "name": "PAWA254 Poster-Making Sprint",
        "category_slug": "workshops-and-classes",
        "venue": "PAWA254",
        "schedule": ("days", 12, 10),
        "duration_days": 0,
        "price": Decimal("2200"),
        "ticketing_enabled": True,
        "available_tickets": 28,
        "going_count": 93,
        "has_gallery": False,
        "description": "PAWA254 runs a hands-on poster-making sprint for campaign graphics, gig flyers, and community notices. The KES 2,200 ticket is useful because participants leave with a finished print-ready layout. Bring a laptop if you have one and one message you want to turn into a poster. The downstairs wall examples are worth studying before the first exercise starts.",
    },
    {
        "name": "The Hub Karen Kids Coding Lab",
        "category_slug": "workshops-and-classes",
        "venue": "The Hub Karen",
        "schedule": ("days", 24, 11),
        "duration_days": 0,
        "price": Decimal("3000"),
        "ticketing_enabled": True,
        "available_tickets": 36,
        "going_count": 112,
        "has_gallery": False,
        "description": "The Hub Karen hosts a beginner coding lab for kids using small games and visual programming exercises. The KES 3,000 ticket includes facilitator support and enough structure for first-timers. Bring a laptop, charger, and a packed snack for the mid-session break. Parents who wait nearby usually get the quietest seats near the bookstore side.",
    },
    {
        "name": "GoDown Design Pop-Up Weekend",
        "category_slug": "markets-and-popups",
        "venue": "GoDown Arts Centre",
        "schedule": ("days", 22, 11),
        "duration_days": 2,
        "price": Decimal("700"),
        "ticketing_enabled": False,
        "available_tickets": None,
        "going_count": 173,
        "has_gallery": False,
        "description": "GoDown Arts Centre gathers furniture makers, illustrators, textile studios, and small publishers for a two-day design pop-up. The KES 700 entry keeps the crowd intentional while still leaving room to browse slowly. Carry cash, a tote, and measurements if you are shopping for home pieces. The best one-off prints usually sit in flat files rather than on the front tables.",
    },
    {
        "name": "Alliance Française Francophone Film Weekend",
        "category_slug": "travel",
        "venue": "Alliance Française",
        "schedule": ("days", 31, 17),
        "duration_days": 2,
        "price": Decimal("2500"),
        "ticketing_enabled": False,
        "available_tickets": None,
        "going_count": 141,
        "has_gallery": False,
        "description": "Alliance Française screens a weekend of Francophone films that travel through West Africa, the Maghreb, and the Indian Ocean. The KES 2,500 pass is a compact way to get a cultural travel fix without leaving Westlands. Use the external link for the film schedule and carry a light jacket for the courtyard intervals. The cafe conversations between screenings are often better than the official introductions.",
    },
]

# Payment flow test events — not for production
PAYMENT_TEST_EVENTS = [
    {
        "name": "[TEST] Free + External",
        "old_names": ["[TEST] Free + External Link"],
        "category_slug": "concerts-and-nightlife",
        "venue": "Alchemist Bar",
        "price": Decimal("0"),
        "ticketing_enabled": False,
        "available_tickets": None,
        "more_details_url": "https://pursuit.app/demo",
        "has_gallery": False,
    },
    {
        "name": "[TEST] M-Pesa KES 100",
        "old_names": ["[TEST] M-Pesa Standard"],
        "category_slug": "talks-and-ideas",
        "venue": "GoDown Arts Centre",
        "price": Decimal("100"),
        "ticketing_enabled": True,
        "available_tickets": 100,
        "more_details_url": None,
        "has_gallery": False,
    },
    {
        "name": "[TEST] Mid Ticket",
        "old_names": [],
        "category_slug": "culture-and-arts",
        "venue": "Circle Art Gallery",
        "price": Decimal("1500"),
        "ticketing_enabled": True,
        "available_tickets": 100,
        "more_details_url": None,
        "has_gallery": False,
    },
    {
        "name": "[TEST] Premium Ticket",
        "old_names": [],
        "category_slug": "concerts-and-nightlife",
        "venue": "Ngong Racecourse",
        "price": Decimal("3500"),
        "ticketing_enabled": True,
        "available_tickets": 100,
        "more_details_url": None,
        "has_gallery": False,
    },
    {
        "name": "[TEST] Sold Out",
        "old_names": [],
        "category_slug": "workshops-and-classes",
        "venue": "PAWA254",
        "price": Decimal("800"),
        "ticketing_enabled": True,
        "available_tickets": 0,
        "more_details_url": None,
        "has_gallery": False,
    },
    {
        "name": "[TEST] Gallery Event",
        "old_names": ["[TEST] Gallery + External"],
        "category_slug": "culture-and-arts",
        "venue": "Nairobi National Museum",
        "price": Decimal("0"),
        "ticketing_enabled": False,
        "available_tickets": None,
        "more_details_url": "https://pursuit.app/demo",
        "has_gallery": True,
        "gallery_description": "Test gallery for verifying the gallery UI component.",
    },
]

TEST_EVENT_DESCRIPTION = "Test event for Pursuit payment and UI flow testing. Not a real event."


def _fallback_image_url(category_slug, index):
    return f"{FALLBACK_IMAGE_URLS[category_slug]}?auto=format&fit=crop&q=80&w=1080&v={index + 1}"


def _category_slug_for_event(event):
    category = event.category.first()
    if not category:
        return "travel"
    return next((slug for slug, name in CATEGORY_NAMES_BY_SLUG.items() if name == category.name), "travel")


def _price_from_text(text):
    match = re.search(r"KES\s*([0-9,]+)", text or "", re.IGNORECASE)
    if not match:
        return Decimal("0")
    return Decimal(match.group(1).replace(",", ""))


def _going_count(name, index):
    return 12 + ((sum(ord(char) for char in name) + index * 37) % 439)


def _series_name(name):
    lower_name = name.lower()
    if "blankets & wine" in lower_name:
        return "Blankets & Wine"
    if "jazz mondays" in lower_name:
        return "Jazz Mondays at Alchemist"
    if "monday" in lower_name or "weekly" in lower_name:
        return name
    return None


def _gallery_description(name):
    return (
        f"A curated set of photos from previous editions and related moments around {name}. "
        "Includes venue details, crowd scenes, and the kind of atmosphere guests can expect."
    )


def _should_have_gallery(event, existing_gallery_count):
    if existing_gallery_count >= 3:
        return False
    text = f"{event.name} {event.description or ''}".lower()
    return any(word in text for word in ("exhibition", "festival", "gallery", "open studios", "museum", "art week"))


def _venue_link(location_name):
    venue = (location_name or "").split(",")[0].strip()
    return EXTERNAL_LINKS.get(venue, "https://pursuit.app/demo")


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

        curated_events = []
        updated_existing_count = 0
        created_new_count = 0
        test_event_count = 0
        images_count = 0
        galleries_count = 0

        if not os.environ.get("UNSPLASH_ACCESS_KEY"):
            self.stdout.write(
                self.style.WARNING(
                    "UNSPLASH_ACCESS_KEY not set — using fallback images.\n"
                    "Run python manage.py seed_images after adding the key to fetch real images."
                )
            )

        existing_gallery_count = 0
        for index, event in enumerate(Event.objects.exclude(name__contains="[TEST]").prefetch_related("category")):
            category_slug = _category_slug_for_event(event)
            price = event.price or _price_from_text(f"{event.name} {event.description}")
            ticketing_enabled = bool(price > 0 and not event.more_details_url)
            update_fields = {
                "price": price,
                "ticketing_enabled": ticketing_enabled,
                "available_tickets": 20 + (index * 11 % 181) if ticketing_enabled else None,
                "going_count": event.going_count or _going_count(event.name, index),
                "series_name": event.series_name or _series_name(event.name),
            }
            if not event.more_details_url and not ticketing_enabled and index < 4:
                update_fields["more_details_url"] = _venue_link(event.location_name)
            if not event.image:
                update_fields["image"] = fetch_unsplash_image_url(category_slug)
                images_count += 1
            if not event.has_gallery and _should_have_gallery(event, existing_gallery_count):
                update_fields["has_gallery"] = True
                update_fields["gallery_images"] = fetch_unsplash_gallery_images(category_slug, 3)
                update_fields["gallery_description"] = _gallery_description(event.name)
                existing_gallery_count += 1
                galleries_count += 1

            for field, value in update_fields.items():
                setattr(event, field, value)
            event.save(update_fields=[*update_fields.keys(), "is_free", "updated_at"])
            updated_existing_count += 1

        for index, event_data in enumerate([*GENERATED_NAIROBI_EVENTS, *NEW_NAIROBI_EVENTS]):
            venue_data = VENUES[event_data["venue"]]
            category_name = CATEGORY_NAMES_BY_SLUG[event_data["category_slug"]]
            category = categories.get(category_name)
            if not category:
                self.stdout.write(self.style.WARNING(f"Category '{category_name}' not found — skipping."))
                continue

            start = _generated_start(event_data["schedule"])
            duration_days = event_data["duration_days"]
            end = start + timedelta(days=duration_days) if duration_days else None
            more_details_url = None
            if not event_data["ticketing_enabled"]:
                more_details_url = EXTERNAL_LINKS.get(event_data["venue"], "https://pursuit.app/demo")
            price = event_data.get("price", _price_from_text(event_data["description"]))
            has_gallery = event_data.get("has_gallery", False)

            event, created = Event.objects.update_or_create(
                name=event_data["name"],
                defaults={
                    "description": event_data["description"],
                    "date": start,
                    "end_date": end,
                    "location_name": f"{event_data['venue']}, {venue_data['neighborhood']}",
                    "location": venue_data["point"],
                    "timezone": "Africa/Nairobi",
                    "more_details_url": more_details_url,
                    "price": price,
                    "ticketing_enabled": event_data["ticketing_enabled"],
                    "available_tickets": (
                        event_data.get("available_tickets") if event_data["ticketing_enabled"] and price > 0 else None
                    ),
                    "going_count": event_data.get("going_count", _going_count(event_data["name"], index)),
                    "has_gallery": has_gallery,
                    "gallery_description": event_data.get("gallery_description") if has_gallery else None,
                    "series_name": event_data.get("series_name") or _series_name(event_data["name"]),
                    "is_active": True,
                },
            )
            event.category.set([category])
            if not event.image:
                event.image = fetch_unsplash_image_url(event_data["category_slug"])
                event.save(update_fields=["image"])
                images_count += 1
            if has_gallery and not event.gallery_images:
                event.gallery_images = fetch_unsplash_gallery_images(event_data["category_slug"], 3)
                event.save(update_fields=["gallery_images"])
                galleries_count += 1
            curated_events.append((event, event_data))
            if created and event_data in NEW_NAIROBI_EVENTS:
                created_new_count += 1

        test_start = timezone.localtime(timezone.now()).replace(hour=12, minute=0, second=0, microsecond=0) + timedelta(
            days=2
        )
        for index, event_data in enumerate(PAYMENT_TEST_EVENTS):
            venue_data = VENUES[event_data["venue"]]
            category_name = CATEGORY_NAMES_BY_SLUG[event_data["category_slug"]]
            category = categories.get(category_name)
            if not category:
                self.stdout.write(self.style.WARNING(f"Category '{category_name}' not found — skipping."))
                continue
            existing_old_event = Event.objects.filter(name__in=event_data.get("old_names", [])).first()
            if existing_old_event:
                existing_old_event.name = event_data["name"]
                existing_old_event.save(update_fields=["name", "updated_at"])

            event, _created = Event.objects.update_or_create(
                name=event_data["name"],
                defaults={
                    "description": TEST_EVENT_DESCRIPTION,
                    "date": test_start + timedelta(days=index),
                    "end_date": None,
                    "location_name": f"{event_data['venue']}, {venue_data['neighborhood']}",
                    "location": venue_data["point"],
                    "timezone": "Africa/Nairobi",
                    "more_details_url": event_data["more_details_url"],
                    "price": event_data["price"],
                    "ticketing_enabled": event_data["ticketing_enabled"],
                    "available_tickets": event_data["available_tickets"],
                    "going_count": _going_count(event_data["name"], index),
                    "has_gallery": event_data["has_gallery"],
                    "gallery_description": event_data.get("gallery_description"),
                    "series_name": None,
                    "is_active": True,
                },
            )
            event.category.set([category])
            if event_data["has_gallery"] and not event.gallery_images:
                event.gallery_images = fetch_unsplash_gallery_images(event_data["category_slug"], 3)
                event.save(update_fields=["gallery_images"])
                galleries_count += 1
            test_event_count += 1

        strongest_picks = [
            ("Jazz & Spoken Word at Alchemist", "nairobi", 0, 7),
            ("Nairobi to Coast Travel Clinic", "mombasa", 0, 7),
            ("Blankets & Wine June Picnic", "nairobi", 7, 14),
        ]
        editors_pick_count = 0
        now = timezone.localtime(timezone.now()).replace(microsecond=0)
        for event_name, location_tag, active_from_days, active_until_days in strongest_picks:
            event_data = next((data for event, data in curated_events if event.name == event_name), None)
            event = next((event for event, data in curated_events if event.name == event_name), None)
            if not event or not event_data or not event_data["curator_note"]:
                self.stdout.write(
                    self.style.WARNING(f"Generated event '{event_name}' not found for Editor's Pick — skipping.")
                )
                continue

            active_from = now + timedelta(days=active_from_days)
            active_until = now + timedelta(days=active_until_days)
            existing_pick = EditorsPick.objects.filter(
                location_tag=location_tag,
                active_from__date=active_from.date(),
            ).first()
            defaults = {
                "event": event,
                "active_from": active_from,
                "active_until": active_until,
                "curator_note": event_data["curator_note"],
                "curator_name": event_data["curator_name"],
                "position": 1,
            }
            if existing_pick:
                for field, value in defaults.items():
                    setattr(existing_pick, field, value)
                existing_pick.save(update_fields=[*defaults.keys(), "updated_at"])
            else:
                EditorsPick.objects.create(location_tag=location_tag, **defaults)
            editors_pick_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated {updated_existing_count} existing events, created {created_new_count} new events, "
                f"{images_count} with images fetched this run, {galleries_count} with galleries, "
                f"{test_event_count} test events, {editors_pick_count} EditorsPick records"
            )
        )

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

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {created_count} events ({skipped_count} already existed), "
                f"{near_term_count} near-term events."
            )
        )

        # --- Seed Editor's Picks ---
        picks_data = [
            # Nairobi - active now
            (
                "Wildlife Photography Masterclass",
                "nairobi",
                0,
                14,
                "Nakuru National Park offers some of East Africa\u2019s most stunning wildlife backdrops \u2014 this workshop is a rare chance to learn from award-winning pros who know every corner of the park. Perfect for serious hobbyists and aspiring pros alike.",
                "Amani, Pursuit Editor",
            ),
            # Mombasa - active now
            (
                "Mombasa Street Food Festival",
                "mombasa",
                0,
                14,
                "The coastal street food scene is unlike anywhere else in Kenya \u2014 come hungry and expect biryani that rivals Zanzibar\u2019s best. The viazi karai alone is worth the trip.",
                "Joy, Pursuit Food Editor",
            ),
            # Kisumu - active in 2 weeks
            (
                "Kisumu Fish Festival",
                "kisumu",
                14,
                21,
                "Lake Victoria\u2019s fishing heritage comes alive in this two-day lakeside celebration. Don\u2019t miss the omena tastings \u2014 crispy, fresh, and served with ugali on the shore.",
                "Kofi, Pursuit Culture Editor",
            ),
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
                },
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

        self.stdout.write(
            self.style.SUCCESS(f"Seeded {picks_created} Editor's Picks ({picks_skipped} already existed).")
        )

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
