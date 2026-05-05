# Generated manually on 2026-05-02
from django.db import migrations
import uuid


# New 8-category taxonomy
NEW_CATEGORIES = [
    {
        "name": "Talks & Ideas",
        "slug": "talks-and-ideas",
        "icon": "💬",
        "description": "Lectures, panels, and conversations worth showing up for",
        "color": "#FECA57",
        "sort_order": 0,
    },
    {
        "name": "Workshops & Classes",
        "slug": "workshops-and-classes",
        "icon": "🛠️",
        "description": "Hands-on learning and skill-building",
        "color": "#96CEB4",
        "sort_order": 1,
    },
    {
        "name": "Concerts & Nightlife",
        "slug": "concerts-and-nightlife",
        "icon": "🎵",
        "description": "Live music and nights out",
        "color": "#54A0FF",
        "sort_order": 2,
    },
    {
        "name": "Culture & Arts",
        "slug": "culture-and-arts",
        "icon": "🎭",
        "description": "Exhibitions, theatre, film, and gallery openings",
        "color": "#FF6B6B",
        "sort_order": 3,
    },
    {
        "name": "Outdoors & Active",
        "slug": "outdoors-and-active",
        "icon": "🏔️",
        "description": "Anything outside or physical",
        "color": "#4ECDC4",
        "sort_order": 4,
    },
    {
        "name": "Food & Drink",
        "slug": "food-and-drink",
        "icon": "🍜",
        "description": "Food festivals, tastings, and supper clubs",
        "color": "#45B7D1",
        "sort_order": 5,
    },
    {
        "name": "Markets & Pop-ups",
        "slug": "markets-and-popups",
        "icon": "🛍️",
        "description": "Markets, fairs, and pop-up moments",
        "color": "#FF9FF3",
        "sort_order": 6,
    },
    {
        "name": "Travel",
        "slug": "travel",
        "icon": "✈️",
        "description": "Trips and destination experiences",
        "color": "#5F27CD",
        "sort_order": 7,
    },
]


# Old category → new category mapping for Events
EVENT_CATEGORY_MAP = {
    "Travel": "Travel",
    "Adventure": "Outdoors & Active",
    "Food & Drink": "Food & Drink",
    "Culture": "Culture & Arts",
    "Learning": None,  # Split based on keywords
    "Sports": "Outdoors & Active",
    "Music & Events": "Concerts & Nightlife",
    "Nature": "Outdoors & Active",
}


# Interest name → new category mapping
INTEREST_CATEGORY_MAP = {
    "Arts & Crafts": "Workshops & Classes",
    "Camping": "Outdoors & Active",
    "Coffee Culture": "Food & Drink",
    "Concerts": "Concerts & Nightlife",
    "Cooking": "Workshops & Classes",
    "Cycling": "Outdoors & Active",
    "Dancing": "Concerts & Nightlife",
    "Gardening": "Workshops & Classes",
    "Hiking": "Outdoors & Active",
    "Learn Languages": "Workshops & Classes",
    "Martial Arts": "Outdoors & Active",
    "Museums": "Culture & Arts",
    "Music": "Concerts & Nightlife",
    "Musical Instruments": "Workshops & Classes",
    "Painting": "Workshops & Classes",
    "Photography": "Workshops & Classes",
    "Programming": "Talks & Ideas",
    "Reading": "Talks & Ideas",
    "Rock Climbing": "Outdoors & Active",
    "Running": "Outdoors & Active",
    "Scuba Diving": "Outdoors & Active",
    "Skydiving": "Outdoors & Active",
    "Surfing": "Outdoors & Active",
    "Swimming": "Outdoors & Active",
    "Theater": "Culture & Arts",
    "Travel": "Travel",
    "Volunteering": "Talks & Ideas",
    "Wine Tasting": "Food & Drink",
    "Writing": "Workshops & Classes",
    "Yoga": "Outdoors & Active",
}


def is_workshop_or_class_event(event_name, event_description):
    """Check if event contains workshop/class keywords (for Learning split)."""
    keywords = ["workshop", "class", "masterclass", "hands-on", "course", "training", "lesson"]
    search_text = f"{event_name} {event_description or ''}".lower()
    return any(kw in search_text for kw in keywords)


def forward(apps, schema_editor):
    """Refactor categories, remap events and interests, delete old categories."""
    Category = apps.get_model("core", "Category")
    Interest = apps.get_model("core", "Interest")
    Event = apps.get_model("events", "Event")

    # Store old categories by name before creating new ones
    old_categories = {cat.name: cat for cat in Category.objects.all()}

    # 1. Create 8 new categories (or reuse if already exists, e.g., Food & Drink, Travel)
    new_categories = {}
    created_count = 0
    for cat_data in NEW_CATEGORIES:
        # Check if category already exists (e.g., Food & Drink, Travel)
        existing = old_categories.get(cat_data["name"])
        if existing:
            # Update the existing category with new attributes
            existing.icon = cat_data["icon"]
            existing.description = cat_data["description"]
            existing.color = cat_data["color"]
            existing.sort_order = cat_data["sort_order"]
            existing.is_active = True
            existing.save(update_fields=["icon", "description", "color", "sort_order", "is_active"])
            new_categories[cat_data["name"]] = existing
            print(f"Reused existing category: {cat_data['name']}")
        else:
            cat = Category.objects.create(
                id=uuid.uuid4(),
                name=cat_data["name"],
                icon=cat_data["icon"],
                description=cat_data["description"],
                color=cat_data["color"],
                sort_order=cat_data["sort_order"],
                is_active=True,
            )
            new_categories[cat_data["name"]] = cat
            created_count += 1

    print(f"Created {created_count} new categories, reused {len(new_categories) - created_count}")

    # 2. Remap Events to new categories
    event_count = 0
    for event in Event.objects.prefetch_related("category").all():
        # Get old categories this event belongs to
        old_event_cats = list(event.category.all())
        new_event_cats = set()

        for old_cat in old_event_cats:
            new_cat_name = EVENT_CATEGORY_MAP.get(old_cat.name)

            # Handle Learning split
            if old_cat.name == "Learning":
                if is_workshop_or_class_event(event.name, event.description):
                    new_cat_name = "Workshops & Classes"
                else:
                    new_cat_name = "Talks & Ideas"

            if new_cat_name and new_cat_name in new_categories:
                new_event_cats.add(new_categories[new_cat_name])

        # Clear old categories and add new ones
        event.category.clear()
        for cat in new_event_cats:
            event.category.add(cat)

        event_count += 1

    print(f"Remapped {event_count} events to new categories")

    # 3. Remap Interests to new categories
    interest_count = 0
    unmapped_interests = []

    for interest in Interest.objects.all():
        new_cat_name = INTEREST_CATEGORY_MAP.get(interest.name)

        if new_cat_name and new_cat_name in new_categories:
            interest.category = new_categories[new_cat_name]
            interest.save(update_fields=["category"])
            interest_count += 1
        else:
            unmapped_interests.append(interest.name)
            # Leave category as-is (will likely be null after old categories deleted)

    print(f"Remapped {interest_count} interests to new categories")
    if unmapped_interests:
        print(f"Warning: {len(unmapped_interests)} interests not in map: {unmapped_interests}")

    # 4. Verify all Events and Interests now point to new categories
    orphaned_events = []
    for event in Event.objects.prefetch_related("category").all():
        if event.category.count() == 0:
            orphaned_events.append(event.name)

    if orphaned_events:
        raise Exception(f"Found {len(orphaned_events)} events with no categories: {orphaned_events[:5]}")

    orphaned_interests = Interest.objects.filter(category__isnull=True).values_list("name", flat=True)
    if orphaned_interests:
        print(f"Warning: {len(orphaned_interests)} interests have no category: {list(orphaned_interests)}")

    # 5. Delete old categories that are NOT in the new set (M2M relationships already cleared)
    new_category_names = set(new_categories.keys())
    old_cats_to_delete = [cat for name, cat in old_categories.items() if name not in new_category_names]
    old_cat_ids = [cat.id for cat in old_cats_to_delete]
    deleted_count, _ = Category.objects.filter(id__in=old_cat_ids).delete()
    print(f"Deleted {deleted_count} old categories")

    # 6. Verify UserProfile.saved_events is unaffected (sanity check)
    # UserEvents references Event, not Category, so should be fine
    UserEvents = apps.get_model("events", "UserEvents")
    saved_event_count = UserEvents.objects.count()
    print(f"Verified {saved_event_count} saved events remain intact")

    # 7. Log distribution across new categories
    print("\nNew category distribution:")
    for cat_name, cat in new_categories.items():
        event_count = Event.objects.filter(category=cat).count()
        interest_count = Interest.objects.filter(category=cat).count()
        print(f"  {cat_name}: {event_count} events, {interest_count} interests")


def reverse(apps, schema_editor):
    """
    Reverse migration: recreate approximate old categories and remap.

    Note: This is approximate. The Learning split cannot be perfectly reversed
    since we don't know which events were originally Learning vs which were
    auto-categorized. We'll map both Workshops & Classes and Talks & Ideas
    back to Learning.
    """
    Category = apps.get_model("core", "Category")
    Interest = apps.get_model("core", "Interest")
    Event = apps.get_model("events", "Event")

    # Delete new categories first
    new_cat_names = [cat["name"] for cat in NEW_CATEGORIES]
    Category.objects.filter(name__in=new_cat_names).delete()

    # Recreate old categories (approximate)
    old_categories_data = [
        {"name": "Travel", "icon": "✈️", "description": "Travel destinations and experiences", "color": "#FF6B6B", "sort_order": 0},
        {"name": "Adventure", "icon": "🏔️", "description": "Outdoor adventures and extreme activities", "color": "#4ECDC4", "sort_order": 1},
        {"name": "Food & Drink", "icon": "🍜", "description": "Culinary experiences and local cuisine", "color": "#45B7D1", "sort_order": 2},
        {"name": "Culture", "icon": "🎭", "description": "Cultural events and artistic experiences", "color": "#96CEB4", "sort_order": 3},
        {"name": "Learning", "icon": "📚", "description": "Educational experiences and skill building", "color": "#FECA57", "sort_order": 4},
        {"name": "Sports", "icon": "⚽", "description": "Sports activities and events", "color": "#FF9FF3", "sort_order": 5},
        {"name": "Music & Events", "icon": "🎵", "description": "Concerts, festivals, and live events", "color": "#54A0FF", "sort_order": 6},
        {"name": "Nature", "icon": "🌿", "description": "Nature experiences and wildlife", "color": "#5F27CD", "sort_order": 7},
    ]

    old_categories = {}
    for cat_data in old_categories_data:
        cat = Category.objects.create(
            id=uuid.uuid4(),
            name=cat_data["name"],
            icon=cat_data["icon"],
            description=cat_data["description"],
            color=cat_data["color"],
            sort_order=cat_data["sort_order"],
            is_active=True,
        )
        old_categories[cat_data["name"]] = cat

    # Reverse map: new → old
    reverse_event_map = {
        "Travel": "Travel",
        "Outdoors & Active": "Adventure",  # Approximate
        "Food & Drink": "Food & Drink",
        "Culture & Arts": "Culture",
        "Talks & Ideas": "Learning",  # Approximate merge
        "Workshops & Classes": "Learning",  # Approximate merge
        "Concerts & Nightlife": "Music & Events",
        "Markets & Pop-ups": "Culture",  # Approximate
    }

    # Remap events
    for event in Event.objects.prefetch_related("category").all():
        current_cats = list(event.category.all())
        event.category.clear()

        for cat in current_cats:
            old_cat_name = reverse_event_map.get(cat.name)
            if old_cat_name and old_cat_name in old_categories:
                event.category.add(old_categories[old_cat_name])

    # Reverse map for interests
    reverse_interest_map = {
        "Workshops & Classes": "Learning",
        "Outdoors & Active": "Adventure",
        "Food & Drink": "Food & Drink",
        "Concerts & Nightlife": "Music & Events",
        "Talks & Ideas": "Learning",
        "Culture & Arts": "Culture",
        "Travel": "Travel",
    }

    # Remap interests
    for interest in Interest.objects.all():
        if interest.category:
            old_cat_name = reverse_interest_map.get(interest.category.name)
            if old_cat_name and old_cat_name in old_categories:
                interest.category = old_categories[old_cat_name]
                interest.save(update_fields=["category"])

    print(f"Reversed to {len(old_categories)} old categories (approximate)")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0004_delete_emoji_rename_emoji_category_icon"),
        ("events", "0007_add_curator_fields"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
