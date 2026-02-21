import graphene

from apps.buckets.models import BucketItem
from apps.core.models import Category
from apps.recommendations.models import Recommendation

from .models import HomeData, UserInsight, WeatherData


class WeatherType(graphene.ObjectType):
    """GraphQL Weather type"""

    city = graphene.String()
    condition = graphene.String()
    temperature = graphene.Float()


class DestinationType(graphene.ObjectType):
    """GraphQL Destination type"""

    location = graphene.String()
    days_away = graphene.Int()


class ProgressType(graphene.ObjectType):
    """GraphQL Progress type"""

    remaining = graphene.Int()
    completed = graphene.Int()
    yearly_goal = graphene.Int()
    percentage = graphene.Int()


class InsightsDataType(graphene.ObjectType):
    """GraphQL InsightsData type"""

    id = graphene.String()
    weather = graphene.Field(WeatherType)
    next_destination = graphene.Field(DestinationType)
    progress = graphene.Field(ProgressType)
    recent_achievement = graphene.String()


class HomeDataType(graphene.ObjectType):
    """GraphQL HomeData type"""

    id = graphene.String()
    greeting = graphene.String()
    time_of_day = graphene.String()
    weather = graphene.Field(WeatherType)
    insights = graphene.Field(InsightsDataType)
    bucket_categories = graphene.List("apps.core.schema.CategoryType")
    recommendations = graphene.List("apps.recommendations.schema.RecommendationType")
    upcoming = graphene.List("apps.buckets.schema.BucketItemType")


class InsightsQueries(graphene.ObjectType):
    """Insights GraphQL queries"""

    get_insights_data = graphene.Field(InsightsDataType)
    get_home = graphene.Field(HomeDataType, offset=graphene.Int(), limit=graphene.Int())

    def resolve_get_insights_data(self, info):
        user = info.context.user
        if not user.is_authenticated:
            return None

        # Get or create user insight
        insight, created = UserInsight.objects.get_or_create(user=user)

        # Get weather data (mock for now)
        weather = WeatherData.objects.filter(city=insight.current_city or "New York").first()
        if not weather:
            weather = WeatherData(city="New York", condition="Sunny", temperature=72)

        return InsightsDataType(
            id=str(insight.id),
            weather=WeatherType(city=weather.city, condition=weather.condition, temperature=weather.temperature),
            next_destination=DestinationType(
                location=insight.next_destination or "Paris, France", days_away=insight.days_to_next_trip or 45
            ),
            progress=ProgressType(
                remaining=insight.remaining_items,
                completed=insight.completed_items,
                yearly_goal=insight.yearly_goal,
                percentage=insight.progress_percentage,
            ),
            recent_achievement=insight.recent_achievement or "Visited 3 new cities this month!",
        )

    def resolve_get_home(self, info, offset=0, limit=10):
        user = info.context.user
        if not user.is_authenticated:
            return None

        # Get home data
        home_data, created = HomeData.objects.get_or_create(user=user)

        # Get insight data
        insight, created = UserInsight.objects.get_or_create(user=user)

        # Get weather data
        weather = WeatherData.objects.filter(city=insight.current_city or "New York").first()
        if not weather:
            weather = WeatherData(city="New York", condition="Sunny", temperature=72)

        return HomeDataType(
            id=str(home_data.id),
            greeting=f"Hello, {user.first_name}",
            time_of_day=home_data.time_of_day,
            weather=WeatherType(city=weather.city, condition=weather.condition, temperature=weather.temperature),
            insights=InsightsDataType(
                id=str(insight.id),
                weather=WeatherType(city=weather.city, condition=weather.condition, temperature=weather.temperature),
                next_destination=DestinationType(
                    location=insight.next_destination or "Paris, France", days_away=insight.days_to_next_trip or 45
                ),
                progress=ProgressType(
                    remaining=insight.remaining_items,
                    completed=insight.completed_items,
                    yearly_goal=insight.yearly_goal,
                    percentage=insight.progress_percentage,
                ),
                recent_achievement=insight.recent_achievement or "Visited 3 new cities this month!",
            ),
            bucket_categories=Category.objects.filter(is_active=True)[:6],
            recommendations=Recommendation.objects.filter(is_active=True, is_featured=True)[:5],
            upcoming=BucketItem.objects.filter(
                bucket_list__user=user, is_completed=False, target_date__isnull=False
            ).order_by("target_date")[:5],
        )
