from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.buckets.models import BucketItem, BucketList
from apps.core.models import Category
from apps.insights.models import UserInsight

User = get_user_model()


class Command(BaseCommand):
    help = "Populate data for a specific user by email"

    def add_arguments(self, parser):
        parser.add_argument("email", type=str, help="Email of the user to populate data for")

    def handle(self, *args, **kwargs):
        email = kwargs["email"]

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User with email {email} does not exist"))
            return

        self.stdout.write(f"Populating data for user: {user.email}")

        # Get categories
        categories = {cat.name: cat for cat in Category.objects.all()}

        if not categories:
            self.stdout.write(self.style.ERROR("No categories found. Run populate_sample_data first."))
            return

        # Create bucket list for user
        bucket_list, created = BucketList.objects.get_or_create(
            user=user, is_default=True, defaults={"name": "My Bucket List", "description": "My adventure bucket list"}
        )

        if created:
            self.stdout.write(self.style.SUCCESS("Created default bucket list"))
        else:
            self.stdout.write("Bucket list already exists")

        # Create sample bucket items with target dates
        bucket_items_data = [
            {
                "title": "Learn to surf in Bali",
                "description": "Take surfing lessons at Bondi Beach",
                "estimated_cost": 2800,
                "location": "Bali, Indonesia",
                "category": "Travelling",
                "target_date": datetime.now().date() + timedelta(days=45),
            },
            {
                "title": "Skydiving in Dubai",
                "description": "Experience the thrill of skydiving",
                "estimated_cost": 1450,
                "location": "Dubai, UAE",
                "category": "Travelling",
                "target_date": datetime.now().date() + timedelta(days=60),
            },
            {
                "title": "Visit the Grand Canyon",
                "description": "Explore one of the world's natural wonders",
                "estimated_cost": 1800,
                "location": "Arizona, USA",
                "category": "Travelling",
                "target_date": datetime.now().date() + timedelta(days=30),
            },
            {
                "title": "Read 24 books this year",
                "description": "Focus on personal development and fiction",
                "estimated_cost": 480,
                "category": "Books",
                "target_date": datetime.now().date() + timedelta(days=90),
            },
            {
                "title": "Learn to play the guitar",
                "description": "Master basic guitar chords and songs",
                "estimated_cost": 650,
                "category": "Music",
                "target_date": datetime.now().date() + timedelta(days=120),
            },
        ]

        created_count = 0
        for item_data in bucket_items_data:
            category_name = item_data.pop("category")
            category = categories.get(category_name)

            _, created = BucketItem.objects.get_or_create(
                bucket_list=bucket_list,
                title=item_data["title"],
                defaults={
                    **item_data,
                    "category": category,
                },
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Created {created_count} new bucket items"))

        # Create or update user insights
        insight, created = UserInsight.objects.get_or_create(
            user=user,
            defaults={
                "total_bucket_items": BucketItem.objects.filter(bucket_list__user=user).count(),
                "completed_items": BucketItem.objects.filter(bucket_list__user=user, is_completed=True).count(),
                "yearly_goal": 25,
                "current_city": "San Francisco",
                "next_destination": "Bali, Indonesia",
                "days_to_next_trip": 45,
                "recent_achievement": "Started your bucket list journey!",
            },
        )

        if not created:
            # Update counts if insight already exists
            insight.total_bucket_items = BucketItem.objects.filter(bucket_list__user=user).count()
            insight.completed_items = BucketItem.objects.filter(bucket_list__user=user, is_completed=True).count()
            insight.save()
            self.stdout.write("Updated user insights")
        else:
            self.stdout.write(self.style.SUCCESS("Created user insights"))

        self.stdout.write(self.style.SUCCESS(f"Data population completed for {user.email}!"))
