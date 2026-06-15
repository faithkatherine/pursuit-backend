from django.core.management.base import BaseCommand

from apps.core.models import Category, Interest


class Command(BaseCommand):
    """Load initial data for the application"""

    help = "Load initial data including categories, icons, and interests"

    def handle(self, *args, **options):
        self.stdout.write("Loading initial data...")

        self.load_categories()
        # self.load_icons()  # Icon model removed
        self.load_interests()

        self.stdout.write(self.style.SUCCESS("Successfully loaded initial data!"))

    def load_categories(self):
        """Create default bucket list categories"""
        categories_data = [
            {
                "name": "Talks & Ideas",
                "icon": "💬",
                "description": "Lectures, panels, and conversations worth showing up for",
                "color": "#FECA57",
            },
            {
                "name": "Workshops & Classes",
                "icon": "🛠️",
                "description": "Hands-on learning and skill-building",
                "color": "#96CEB4",
            },
            {
                "name": "Concerts & Nightlife",
                "icon": "🎵",
                "description": "Live music and nights out",
                "color": "#54A0FF",
            },
            {
                "name": "Culture & Arts",
                "icon": "🎭",
                "description": "Exhibitions, theatre, film, and gallery openings",
                "color": "#FF6B6B",
            },
            {
                "name": "Outdoors & Active",
                "icon": "🏔️",
                "description": "Anything outside or physical",
                "color": "#4ECDC4",
            },
            {
                "name": "Food & Drink",
                "icon": "🍜",
                "description": "Food festivals, tastings, and supper clubs",
                "color": "#45B7D1",
            },
            {
                "name": "Markets & Pop-ups",
                "icon": "🛍️",
                "description": "Markets, fairs, and pop-up moments",
                "color": "#FF9FF3",
            },
            {
                "name": "Travel",
                "icon": "✈️",
                "description": "Trips and destination experiences",
                "color": "#5F27CD",
            },
        ]

        for i, cat_data in enumerate(categories_data):
            category, created = Category.objects.get_or_create(
                name=cat_data["name"],
                defaults={
                    "icon": cat_data["icon"],
                    "description": cat_data["description"],
                    "color": cat_data["color"],
                    "sort_order": i,
                },
            )
            if created:
                self.stdout.write(f"Created category: {category.name}")

    def load_icons(self):  # noqa: C901
        """Create icon library — DISABLED: Icon model has been removed"""
        self.stdout.write(self.style.WARNING("Skipping icon loading — Icon model not available"))
        return

    def load_interests(self):
        """Create user interests for personalization, linked to categories"""
        # Map interest names to their parent category
        interest_category_map = {
            "Travel": "Travel",
            "Hiking": "Outdoors & Active",
            "Camping": "Outdoors & Active",
            "Scuba Diving": "Outdoors & Active",
            "Skydiving": "Outdoors & Active",
            "Rock Climbing": "Outdoors & Active",
            "Cooking": "Workshops & Classes",
            "Wine Tasting": "Food & Drink",
            "Coffee Culture": "Food & Drink",
            "Photography": "Workshops & Classes",
            "Painting": "Workshops & Classes",
            "Theater": "Culture & Arts",
            "Museums": "Culture & Arts",
            "Volunteering": "Talks & Ideas",
            "Reading": "Talks & Ideas",
            "Learn Languages": "Workshops & Classes",
            "Programming": "Talks & Ideas",
            "Writing": "Workshops & Classes",
            "Arts & Crafts": "Workshops & Classes",
            "Running": "Outdoors & Active",
            "Yoga": "Outdoors & Active",
            "Swimming": "Outdoors & Active",
            "Cycling": "Outdoors & Active",
            "Martial Arts": "Outdoors & Active",
            "Surfing": "Outdoors & Active",
            "Music": "Concerts & Nightlife",
            "Concerts": "Concerts & Nightlife",
            "Dancing": "Concerts & Nightlife",
            "Musical Instruments": "Workshops & Classes",
            "Gardening": "Workshops & Classes",
        }

        # Pre-fetch categories for linking
        categories = {c.name: c for c in Category.objects.all()}

        interests_data = [
            # Travel
            {"name": "Travel", "icon": "✈️", "description": "Exploring new destinations and cultures"},
            # Adventure
            {"name": "Hiking", "icon": "🥾", "description": "Outdoor hiking and trekking adventures"},
            {"name": "Camping", "icon": "🏕️", "description": "Outdoor camping experiences"},
            {"name": "Scuba Diving", "icon": "🤿", "description": "Underwater diving adventures"},
            {"name": "Skydiving", "icon": "🪂", "description": "Skydiving and aerial adventures"},
            {"name": "Rock Climbing", "icon": "🧗", "description": "Indoor and outdoor climbing"},
            # Food & Drink
            {"name": "Cooking", "icon": "👨\u200d🍳", "description": "Culinary arts and cooking"},
            {"name": "Wine Tasting", "icon": "🍷", "description": "Wine appreciation and tasting"},
            {"name": "Coffee Culture", "icon": "☕", "description": "Coffee appreciation and cafe culture"},
            # Culture
            {"name": "Photography", "icon": "📸", "description": "Capturing moments through photography"},
            {"name": "Painting", "icon": "🎨", "description": "Artistic painting and drawing"},
            {"name": "Theater", "icon": "🎭", "description": "Theater performances and acting"},
            {"name": "Museums", "icon": "🏛️", "description": "Visiting museums and galleries"},
            {"name": "Volunteering", "icon": "🤝", "description": "Community service and volunteering"},
            # Learning
            {"name": "Reading", "icon": "📚", "description": "Reading books and literature"},
            {"name": "Learn Languages", "icon": "🗣️", "description": "Learning new languages"},
            {"name": "Programming", "icon": "💻", "description": "Coding and software development"},
            {"name": "Writing", "icon": "✍️", "description": "Creative and professional writing"},
            {"name": "Arts & Crafts", "icon": "🧵", "description": "Handmade crafts and DIY projects"},
            # Sports
            {"name": "Running", "icon": "🏃", "description": "Running and jogging activities"},
            {"name": "Yoga", "icon": "🧘", "description": "Yoga practice and mindfulness"},
            {"name": "Swimming", "icon": "🏊", "description": "Swimming and water activities"},
            {"name": "Cycling", "icon": "🚴", "description": "Cycling and biking adventures"},
            {"name": "Martial Arts", "icon": "🥋", "description": "Martial arts training"},
            {"name": "Surfing", "icon": "🏄", "description": "Surfing and water sports"},
            # Music & Events
            {"name": "Music", "icon": "🎵", "description": "Music appreciation and creation"},
            {"name": "Concerts", "icon": "🎤", "description": "Live music and concert experiences"},
            {"name": "Dancing", "icon": "💃", "description": "Dance styles and performances"},
            {"name": "Musical Instruments", "icon": "🎸", "description": "Learning musical instruments"},
            # Nature
            {"name": "Gardening", "icon": "🌱", "description": "Gardening and plant care"},
        ]

        for interest_data in interests_data:
            category_name = interest_category_map.get(interest_data["name"])
            category = categories.get(category_name)
            interest, created = Interest.objects.get_or_create(
                name=interest_data["name"],
                defaults={
                    "icon": interest_data["icon"],
                    "description": interest_data["description"],
                    "category": category,
                },
            )
            if not created and interest.category is None and category is not None:
                interest.category = category
                interest.save(update_fields=["category"])
                self.stdout.write(f"Linked interest: {interest.icon} {interest.name} -> {category_name}")
            elif created:
                self.stdout.write(f"Created interest: {interest.icon} {interest.name} -> {category_name}")
