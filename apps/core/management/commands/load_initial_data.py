from django.core.management.base import BaseCommand
from apps.core.models import Category, Emoji


class Command(BaseCommand):
    """Load initial data for the application"""
    
    help = 'Load initial data including categories and emojis'
    
    def handle(self, *args, **options):
        self.stdout.write('Loading initial data...')
        
        # Create default categories
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
        
        # Create emoji library
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
            emoji, created = Emoji.objects.get_or_create(
                symbol=symbol,
                defaults={
                    'description': description,
                    'category': category,
                    'unicode_value': f'U+{ord(symbol):04X}'
                }
            )
            if created:
                self.stdout.write(f'Created emoji: {emoji.symbol} - {emoji.description}')
        
        self.stdout.write(
            self.style.SUCCESS('Successfully loaded initial data!')
        )
