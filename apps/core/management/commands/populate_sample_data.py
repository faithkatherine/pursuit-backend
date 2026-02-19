from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.buckets.models import BucketItem, BucketList
from apps.core.models import Category
from apps.insights.models import UserInsight, WeatherData
from apps.recommendations.models import Recommendation

User = get_user_model()


class Command(BaseCommand):
    help = 'Populate database with sample data for demo'

    def handle(self, *args, **kwargs):
        self.stdout.write('Starting to populate sample data...')

        # Create or get a demo user (or use existing authenticated user)
        user, created = User.objects.get_or_create(
            email='demo@pursuit.com',
            defaults={
                'username': 'demo',
                'first_name': 'Demo',
                'last_name': 'User',
                'is_active': True
            }
        )
        if created:
            user.set_password('demo123')
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Created demo user: {user.email}'))

        # Create categories
        categories_data = [
            {"name": "Movies", "emoji": "🎬"},
            {"name": "Books", "emoji": "📚"},
            {"name": "Cooking", "emoji": "🍳"},
            {"name": "Travelling", "emoji": "✈️"},
            {"name": "Fitness", "emoji": "⚽"},
            {"name": "Creativity", "emoji": "🎨"},
            {"name": "Music", "emoji": "🎵"},
            {"name": "Nature", "emoji": "🌿"},
        ]

        categories = {}
        for cat_data in categories_data:
            cat, created = Category.objects.get_or_create(
                name=cat_data["name"],
                defaults={"emoji": cat_data["emoji"], "is_active": True}
            )
            categories[cat_data["name"]] = cat
            if created:
                self.stdout.write(f'Created category: {cat.name}')

        # Create bucket list for demo user
        bucket_list, created = BucketList.objects.get_or_create(
            user=user,
            is_default=True,
            defaults={'name': 'My Bucket List', 'description': 'My adventure bucket list'}
        )
        if created:
            self.stdout.write(self.style.SUCCESS('Created default bucket list'))

        # Create bucket items
        bucket_items_data = [
            # Travel Items
            {
                "title": "Learn to surf in Bali",
                "description": "Take surfing lessons at Bondi Beach",
                "estimated_cost": 2800,
                "location": "Bali, Indonesia",
                "image": "https://images.unsplash.com/photo-1502933691298-84fc14542831?auto=format&fit=crop&q=80&w=800",
                "category": "Travelling",
                "is_completed": False,
            },
            {
                "title": "Skydiving in Dubai",
                "description": "Experience the thrill of skydiving with amazing city views",
                "estimated_cost": 1450,
                "location": "Dubai, UAE",
                "image": "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&q=80&w=800",
                "category": "Travelling",
                "is_completed": False,
            },
            {
                "title": "Visit the Grand Canyon",
                "description": "Explore one of the world's natural wonders",
                "estimated_cost": 1800,
                "location": "Arizona, USA",
                "image": "https://images.unsplash.com/photo-1500534623283-312aade485b7?auto=format&fit=crop&q=80&w=800",
                "category": "Travelling",
                "is_completed": False,
            },
            {
                "title": "Visit the Eiffel Tower",
                "description": "See the iconic landmark in Paris",
                "estimated_cost": 3200,
                "location": "Paris, France",
                "image": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&q=80&w=800",
                "category": "Travelling",
                "is_completed": False,
            },
            {
                "title": "Visit the Taj Mahal",
                "description": "Experience this architectural marvel in India",
                "estimated_cost": 2950,
                "location": "Agra, India",
                "image": "https://images.unsplash.com/photo-1564507592333-c60657eea523?auto=format&fit=crop&q=80&w=800",
                "category": "Travelling",
                "is_completed": False,
            },
            # Books Items
            {
                "title": "Read 24 books this year",
                "description": "Focus on personal development and fiction",
                "estimated_cost": 480,
                "image": "https://images.unsplash.com/photo-1481627834876-b7833e8f5570?auto=format&fit=crop&q=80&w=800",
                "category": "Books",
                "is_completed": False,
            },
            {
                "title": "Read Dune Series",
                "description": "Complete Frank Herbert's epic sci-fi series",
                "estimated_cost": 120,
                "image": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&q=80&w=800",
                "category": "Books",
                "is_completed": False,
            },
            # Movies Items
            {
                "title": "Watch Inception",
                "description": "Finally watch this mind-bending movie",
                "image": "https://images.unsplash.com/photo-1489599316546-1c5d71201ae8?auto=format&fit=crop&q=80&w=800",
                "category": "Movies",
                "is_completed": True,
            },
            {
                "title": "Watch Studio Ghibli Collection",
                "description": "Experience all of Miyazaki's masterpieces",
                "estimated_cost": 150,
                "image": "https://images.unsplash.com/photo-1440404653325-ab127d49abc1?auto=format&fit=crop&q=80&w=800",
                "category": "Movies",
                "is_completed": False,
            },
            # Sports & Fitness Items
            {
                "title": "Complete a Marathon",
                "description": "Train for and finish a full 26.2 mile marathon",
                "estimated_cost": 300,
                "image": "https://images.unsplash.com/photo-1571019613540-996a8cfeb0d0?auto=format&fit=crop&q=80&w=800",
                "category": "Fitness",
                "is_completed": False,
            },
            {
                "title": "Learn Rock Climbing",
                "description": "Master indoor and outdoor climbing techniques",
                "estimated_cost": 800,
                "image": "https://images.unsplash.com/photo-1522163182402-834f871fd851?auto=format&fit=crop&q=80&w=800",
                "category": "Fitness",
                "is_completed": False,
            },
            # Arts & Creativity Items
            {
                "title": "Paint a Self-Portrait",
                "description": "Create an oil painting self-portrait",
                "estimated_cost": 200,
                "image": "https://images.unsplash.com/photo-1513475382585-d06e58bcb0e0?auto=format&fit=crop&q=80&w=800",
                "category": "Creativity",
                "is_completed": False,
            },
            {
                "title": "Photography Exhibition",
                "description": "Have my photos displayed in a local gallery",
                "estimated_cost": 500,
                "image": "https://images.unsplash.com/photo-1502920917128-1aa500764cbd?auto=format&fit=crop&q=80&w=800",
                "category": "Creativity",
                "is_completed": False,
            },
            # Music Items
            {
                "title": "Learn to play the guitar",
                "description": "Master basic guitar chords and songs",
                "estimated_cost": 650,
                "image": "https://images.unsplash.com/photo-1511376777868-611b54f68947?auto=format&fit=crop&q=80&w=800",
                "category": "Music",
                "is_completed": False,
            },
            {
                "title": "Attend Coachella",
                "description": "Experience the iconic music festival",
                "estimated_cost": 1200,
                "location": "California, USA",
                "image": "https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?auto=format&fit=crop&q=80&w=800",
                "category": "Music",
                "is_completed": False,
            },
            # Cooking Items
            {
                "title": "Master French Cuisine",
                "description": "Learn to cook classic French dishes",
                "estimated_cost": 400,
                "image": "https://images.unsplash.com/photo-1556909114-4a2b031db544?auto=format&fit=crop&q=80&w=800",
                "category": "Cooking",
                "is_completed": False,
            },
            {
                "title": "Learn Sushi Making",
                "description": "Take professional sushi making classes",
                "estimated_cost": 350,
                "image": "https://images.unsplash.com/photo-1579952363873-27d3bfad9c0d?auto=format&fit=crop&q=80&w=800",
                "category": "Cooking",
                "is_completed": False,
            },
            # Nature Items
            {
                "title": "Hike Machu Picchu",
                "description": "Complete the Inca Trail to Machu Picchu",
                "estimated_cost": 2500,
                "location": "Peru",
                "image": "https://images.unsplash.com/photo-1587595431973-160d0d94add1?auto=format&fit=crop&q=80&w=800",
                "category": "Nature",
                "is_completed": False,
            },
            {
                "title": "Northern Lights in Iceland",
                "description": "Witness the aurora borealis in Iceland",
                "estimated_cost": 3500,
                "location": "Iceland",
                "image": "https://images.unsplash.com/photo-1531366936337-7c912a4589a7?auto=format&fit=crop&q=80&w=800",
                "category": "Nature",
                "is_completed": False,
            },
        ]

        for item_data in bucket_items_data:
            category_name = item_data.pop("category")
            category = categories.get(category_name)

            BucketItem.objects.get_or_create(
                bucket_list=bucket_list,
                title=item_data["title"],
                defaults={
                    **item_data,
                    "category": category,
                }
            )

        self.stdout.write(self.style.SUCCESS(f'Created {len(bucket_items_data)} bucket items'))

        # Create recommendations
        recommendations_data = [
            {
                "title": "Cherry Blossoms in Japan",
                "description": "Experience the beautiful cherry blossom season in Kyoto",
                "location": "Kyoto, Japan",
                "image": "https://images.unsplash.com/photo-1522383225653-ed111181a951?w=400",
                "estimated_cost": 1800,
                "is_featured": True,
                "is_active": True,
                "recommendation_type": "destination",
            },
            {
                "title": "Wine Harvest in Tuscany",
                "description": "Join the grape harvest and wine making in Italian countryside",
                "location": "Tuscany, Italy",
                "image": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400",
                "estimated_cost": 900,
                "is_featured": True,
                "is_active": True,
                "recommendation_type": "experience",
            },
            {
                "title": "Beach Cleanup Event",
                "description": "Join a community beach cleanup initiative",
                "location": "Santa Monica Beach, CA",
                "image": "https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?w=900&auto=format&fit=crop&q=60",
                "estimated_cost": 0,
                "is_featured": True,
                "is_active": True,
                "recommendation_type": "event",
            },
            {
                "title": "Tech Conference 2024",
                "description": "Annual technology conference with industry leaders",
                "location": "Los Angeles Convention Center",
                "image": "https://images.unsplash.com/photo-1459749411175-04bf5292ceea?auto=format&fit=crop&q=80&w=800",
                "estimated_cost": 500,
                "is_featured": True,
                "is_active": True,
                "recommendation_type": "event",
            },
            {
                "title": "Art Exhibition: Modern Masters",
                "description": "Contemporary art exhibition featuring local and international artists",
                "location": "Downtown Art Gallery",
                "image": "https://images.unsplash.com/photo-1527529482837-4698179dc6ce?auto=format&fit=crop&q=80&w=800",
                "estimated_cost": 25,
                "is_featured": True,
                "is_active": True,
                "recommendation_type": "event",
            },
        ]

        for rec_data in recommendations_data:
            Recommendation.objects.get_or_create(
                title=rec_data["title"],
                defaults=rec_data
            )

        self.stdout.write(self.style.SUCCESS(f'Created {len(recommendations_data)} recommendations'))

        # Create weather data
        weather_data = [
            {"city": "San Francisco", "condition": "Sunny", "temperature": 72},
            {"city": "New York", "condition": "Cloudy", "temperature": 65},
            {"city": "Los Angeles", "condition": "Clear", "temperature": 78},
            {"city": "Chicago", "condition": "Windy", "temperature": 58},
        ]

        for weather in weather_data:
            WeatherData.objects.get_or_create(
                city=weather["city"],
                defaults=weather
            )

        self.stdout.write(self.style.SUCCESS('Created weather data'))

        # Create user insights
        insight, created = UserInsight.objects.get_or_create(
            user=user,
            defaults={
                'total_bucket_items': 18,
                'completed_items': 15,
                'yearly_goal': 25,
                'current_city': 'San Francisco',
                'next_destination': 'Tokyo, Japan',
                'days_to_next_trip': 14,
                'recent_achievement': 'Completed hiking challenge',
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS('Created user insights'))

        self.stdout.write(self.style.SUCCESS('Sample data population completed!'))
