from django.core.management.base import BaseCommand

from apps.core.models import Category, icon, Interest


class Command(BaseCommand):
    """Load initial data for the application"""

    help = 'Load initial data including categories, icons, and interests'

    def handle(self, *args, **options):
        self.stdout.write('Loading initial data...')

        self.load_categories()
        self.load_icons()
        self.load_interests()

        self.stdout.write(
            self.style.SUCCESS('Successfully loaded initial data!')
        )

    def load_categories(self):
        """Create default bucket list categories"""
        categories_data = [
            {'name': 'Travel', 'icon': '✈️',
             'description': 'Travel destinations and experiences', 'color': '#FF6B6B'},
            {'name': 'Adventure', 'icon': '🏔️',
             'description': 'Outdoor adventures and extreme activities', 'color': '#4ECDC4'},
            {'name': 'Food & Drink', 'icon': '🍜',
             'description': 'Culinary experiences and local cuisine', 'color': '#45B7D1'},
            {'name': 'Culture', 'icon': '🎭',
             'description': 'Cultural events and artistic experiences', 'color': '#96CEB4'},
            {'name': 'Learning', 'icon': '📚',
             'description': 'Educational experiences and skill building', 'color': '#FECA57'},
            {'name': 'Sports', 'icon': '⚽',
             'description': 'Sports activities and events', 'color': '#FF9FF3'},
            {'name': 'Music & Events', 'icon': '🎵',
             'description': 'Concerts, festivals, and live events', 'color': '#54A0FF'},
            {'name': 'Nature', 'icon': '🌿', 'description': 'Nature experiences and wildlife', 'color': '#5F27CD'},
        ]

        for i, cat_data in enumerate(categories_data):
            category, created = Category.objects.get_or_create(
                name=cat_data['name'],
                defaults={
                    'icon': cat_data['icon'],
                    'description': cat_data['description'],
                    'color': cat_data['color'],
                    'sort_order': i
                }
            )
            if created:
                self.stdout.write(f'Created category: {category.name}')

    def load_icons(self):
        """Create icon library"""
        icons_data = [
            ('✈️', 'Airplane', 'travel'),
            ('🏔️', 'Mountain', 'adventure'),
            ('🍜', 'Noodles', 'food'),
            ('🎭', 'Performing Arts', 'culture'),
            ('📚', 'Books', 'learning'),
            ('⚽', 'Soccer Ball', 'sports'),
            ('🎵', 'Musical Note', 'music'),
            ('🌿', 'Herb', 'nature'),
            ('🏖️', 'Beach', 'travel'),
            ('🎸', 'Guitar', 'music'),
            ('🍕', 'Pizza', 'food'),
            ('🎨', 'Artist Palette', 'culture'),
            ('🏃', 'Running', 'sports'),
            ('📸', 'Camera', 'travel'),
            ('🎪', 'Circus Tent', 'culture'),
            ('🍣', 'Sushi', 'food'),
            ('🏄', 'Surfing', 'adventure'),
            ('🎬', 'Movie Camera', 'culture'),
            ('🧗', 'Climbing', 'adventure'),
            ('🍷', 'Wine Glass', 'food'),
        ]

        for symbol, description, category in icons_data:
            # Handle multi-character icon sequences
            unicode_value = ' '.join(f'U+{ord(char):04X}' for char in symbol)
            icon, created = icon.objects.get_or_create(
                symbol=symbol,
                defaults={
                    'description': description,
                    'category': category,
                    'unicode_value': unicode_value
                }
            )
            if created:
                self.stdout.write(f'Created icon: {icon.symbol} - {icon.description}')

    def load_interests(self):
        """Create user interests for personalization, linked to categories"""
        # Map interest names to their parent category
        interest_category_map = {
            'Travel': 'Travel',
            'Hiking': 'Adventure',
            'Camping': 'Adventure',
            'Scuba Diving': 'Adventure',
            'Skydiving': 'Adventure',
            'Rock Climbing': 'Adventure',
            'Cooking': 'Food & Drink',
            'Wine Tasting': 'Food & Drink',
            'Coffee Culture': 'Food & Drink',
            'Photography': 'Culture',
            'Painting': 'Culture',
            'Theater': 'Culture',
            'Museums': 'Culture',
            'Volunteering': 'Culture',
            'Reading': 'Learning',
            'Learn Languages': 'Learning',
            'Programming': 'Learning',
            'Writing': 'Learning',
            'Arts & Crafts': 'Learning',
            'Running': 'Sports',
            'Yoga': 'Sports',
            'Swimming': 'Sports',
            'Cycling': 'Sports',
            'Martial Arts': 'Sports',
            'Surfing': 'Sports',
            'Music': 'Music & Events',
            'Concerts': 'Music & Events',
            'Dancing': 'Music & Events',
            'Musical Instruments': 'Music & Events',
            'Gardening': 'Nature',
        }

        # Pre-fetch categories for linking
        categories = {c.name: c for c in Category.objects.all()}

        interests_data = [
            # Travel
            {'name': 'Travel', 'icon': '✈️', 'description': 'Exploring new destinations and cultures'},
            # Adventure
            {'name': 'Hiking', 'icon': '🥾', 'description': 'Outdoor hiking and trekking adventures'},
            {'name': 'Camping', 'icon': '🏕️', 'description': 'Outdoor camping experiences'},
            {'name': 'Scuba Diving', 'icon': '🤿', 'description': 'Underwater diving adventures'},
            {'name': 'Skydiving', 'icon': '🪂', 'description': 'Skydiving and aerial adventures'},
            {'name': 'Rock Climbing', 'icon': '🧗', 'description': 'Indoor and outdoor climbing'},
            # Food & Drink
            {'name': 'Cooking', 'icon': '👨\u200d🍳', 'description': 'Culinary arts and cooking'},
            {'name': 'Wine Tasting', 'icon': '🍷', 'description': 'Wine appreciation and tasting'},
            {'name': 'Coffee Culture', 'icon': '☕', 'description': 'Coffee appreciation and cafe culture'},
            # Culture
            {'name': 'Photography', 'icon': '📸', 'description': 'Capturing moments through photography'},
            {'name': 'Painting', 'icon': '🎨', 'description': 'Artistic painting and drawing'},
            {'name': 'Theater', 'icon': '🎭', 'description': 'Theater performances and acting'},
            {'name': 'Museums', 'icon': '🏛️', 'description': 'Visiting museums and galleries'},
            {'name': 'Volunteering', 'icon': '🤝', 'description': 'Community service and volunteering'},
            # Learning
            {'name': 'Reading', 'icon': '📚', 'description': 'Reading books and literature'},
            {'name': 'Learn Languages', 'icon': '🗣️', 'description': 'Learning new languages'},
            {'name': 'Programming', 'icon': '💻', 'description': 'Coding and software development'},
            {'name': 'Writing', 'icon': '✍️', 'description': 'Creative and professional writing'},
            {'name': 'Arts & Crafts', 'icon': '🧵', 'description': 'Handmade crafts and DIY projects'},
            # Sports
            {'name': 'Running', 'icon': '🏃', 'description': 'Running and jogging activities'},
            {'name': 'Yoga', 'icon': '🧘', 'description': 'Yoga practice and mindfulness'},
            {'name': 'Swimming', 'icon': '🏊', 'description': 'Swimming and water activities'},
            {'name': 'Cycling', 'icon': '🚴', 'description': 'Cycling and biking adventures'},
            {'name': 'Martial Arts', 'icon': '🥋', 'description': 'Martial arts training'},
            {'name': 'Surfing', 'icon': '🏄', 'description': 'Surfing and water sports'},
            # Music & Events
            {'name': 'Music', 'icon': '🎵', 'description': 'Music appreciation and creation'},
            {'name': 'Concerts', 'icon': '🎤', 'description': 'Live music and concert experiences'},
            {'name': 'Dancing', 'icon': '💃', 'description': 'Dance styles and performances'},
            {'name': 'Musical Instruments', 'icon': '🎸', 'description': 'Learning musical instruments'},
            # Nature
            {'name': 'Gardening', 'icon': '🌱', 'description': 'Gardening and plant care'},
        ]

        for interest_data in interests_data:
            category_name = interest_category_map.get(interest_data['name'])
            category = categories.get(category_name)
            interest, created = Interest.objects.get_or_create(
                name=interest_data['name'],
                defaults={
                    'icon': interest_data['icon'],
                    'description': interest_data['description'],
                    'category': category,
                }
            )
            if not created and interest.category is None and category is not None:
                interest.category = category
                interest.save(update_fields=['category'])
                self.stdout.write(f'Linked interest: {interest.icon} {interest.name} -> {category_name}')
            elif created:
                self.stdout.write(f'Created interest: {interest.icon} {interest.name} -> {category_name}')
