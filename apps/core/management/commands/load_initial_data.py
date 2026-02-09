from django.core.management.base import BaseCommand
from apps.core.models import Category, Emoji
from apps.users.models import Interest


class Command(BaseCommand):
    """Load initial data for the application"""

    help = 'Load initial data including categories, emojis, and interests'

    def handle(self, *args, **options):
        self.stdout.write('Loading initial data...')

        self.load_categories()
        self.load_emojis()
        self.load_interests()

        self.stdout.write(
            self.style.SUCCESS('Successfully loaded initial data!')
        )

    def load_categories(self):
        """Create default bucket list categories"""
        categories_data = [
            {'name': 'Travel', 'emoji': '✈️', 'description': 'Travel destinations and experiences', 'color': '#FF6B6B'},
            {'name': 'Adventure', 'emoji': '🏔️', 'description': 'Outdoor adventures and extreme activities', 'color': '#4ECDC4'},
            {'name': 'Food & Drink', 'emoji': '🍜', 'description': 'Culinary experiences and local cuisine', 'color': '#45B7D1'},
            {'name': 'Culture', 'emoji': '🎭', 'description': 'Cultural events and artistic experiences', 'color': '#96CEB4'},
            {'name': 'Learning', 'emoji': '📚', 'description': 'Educational experiences and skill building', 'color': '#FECA57'},
            {'name': 'Sports', 'emoji': '⚽', 'description': 'Sports activities and events', 'color': '#FF9FF3'},
            {'name': 'Music & Events', 'emoji': '🎵', 'description': 'Concerts, festivals, and live events', 'color': '#54A0FF'},
            {'name': 'Nature', 'emoji': '🌿', 'description': 'Nature experiences and wildlife', 'color': '#5F27CD'},
        ]

        for i, cat_data in enumerate(categories_data):
            category, created = Category.objects.get_or_create(
                name=cat_data['name'],
                defaults={
                    'emoji': cat_data['emoji'],
                    'description': cat_data['description'],
                    'color': cat_data['color'],
                    'sort_order': i
                }
            )
            if created:
                self.stdout.write(f'Created category: {category.name}')

    def load_emojis(self):
        """Create emoji library"""
        emojis_data = [
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

        for symbol, description, category in emojis_data:
            # Handle multi-character emoji sequences
            unicode_value = ' '.join(f'U+{ord(char):04X}' for char in symbol)
            emoji, created = Emoji.objects.get_or_create(
                symbol=symbol,
                defaults={
                    'description': description,
                    'category': category,
                    'unicode_value': unicode_value
                }
            )
            if created:
                self.stdout.write(f'Created emoji: {emoji.symbol} - {emoji.description}')

    def load_interests(self):
        """Create user interests for personalization"""
        interests_data = [
            # Adventure & Travel
            {'name': 'Travel', 'icon': '✈️', 'description': 'Exploring new destinations and cultures'},
            {'name': 'Hiking', 'icon': '🥾', 'description': 'Outdoor hiking and trekking adventures'},
            {'name': 'Camping', 'icon': '🏕️', 'description': 'Outdoor camping experiences'},
            {'name': 'Scuba Diving', 'icon': '🤿', 'description': 'Underwater diving adventures'},
            {'name': 'Skydiving', 'icon': '🪂', 'description': 'Skydiving and aerial adventures'},
            {'name': 'Rock Climbing', 'icon': '🧗', 'description': 'Indoor and outdoor climbing'},

            # Arts & Culture
            {'name': 'Photography', 'icon': '📸', 'description': 'Capturing moments through photography'},
            {'name': 'Painting', 'icon': '🎨', 'description': 'Artistic painting and drawing'},
            {'name': 'Music', 'icon': '🎵', 'description': 'Music appreciation and creation'},
            {'name': 'Theater', 'icon': '🎭', 'description': 'Theater performances and acting'},
            {'name': 'Museums', 'icon': '🏛️', 'description': 'Visiting museums and galleries'},
            {'name': 'Concerts', 'icon': '🎤', 'description': 'Live music and concert experiences'},

            # Sports & Fitness
            {'name': 'Running', 'icon': '🏃', 'description': 'Running and jogging activities'},
            {'name': 'Yoga', 'icon': '🧘', 'description': 'Yoga practice and mindfulness'},
            {'name': 'Swimming', 'icon': '🏊', 'description': 'Swimming and water activities'},
            {'name': 'Cycling', 'icon': '🚴', 'description': 'Cycling and biking adventures'},
            {'name': 'Martial Arts', 'icon': '🥋', 'description': 'Martial arts training'},
            {'name': 'Surfing', 'icon': '🏄', 'description': 'Surfing and water sports'},

            # Food & Lifestyle
            {'name': 'Cooking', 'icon': '👨‍🍳', 'description': 'Culinary arts and cooking'},
            {'name': 'Wine Tasting', 'icon': '🍷', 'description': 'Wine appreciation and tasting'},
            {'name': 'Coffee Culture', 'icon': '☕', 'description': 'Coffee appreciation and cafe culture'},
            {'name': 'Gardening', 'icon': '🌱', 'description': 'Gardening and plant care'},
            {'name': 'Volunteering', 'icon': '🤝', 'description': 'Community service and volunteering'},
            {'name': 'Reading', 'icon': '📚', 'description': 'Reading books and literature'},

            # Learning & Skills
            {'name': 'Learn Languages', 'icon': '🗣️', 'description': 'Learning new languages'},
            {'name': 'Programming', 'icon': '💻', 'description': 'Coding and software development'},
            {'name': 'Writing', 'icon': '✍️', 'description': 'Creative and professional writing'},
            {'name': 'Dancing', 'icon': '💃', 'description': 'Dance styles and performances'},
            {'name': 'Musical Instruments', 'icon': '🎸', 'description': 'Learning musical instruments'},
            {'name': 'Arts & Crafts', 'icon': '🧵', 'description': 'Handmade crafts and DIY projects'},
        ]

        for interest_data in interests_data:
            interest, created = Interest.objects.get_or_create(
                name=interest_data['name'],
                defaults={
                    'icon': interest_data['icon'],
                    'description': interest_data['description'],
                }
            )
            if created:
                self.stdout.write(f'Created interest: {interest.icon} {interest.name}')
