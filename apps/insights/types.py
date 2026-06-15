import graphene


class WeatherType(graphene.ObjectType):
    """GraphQL Weather type"""

    city = graphene.String()
    condition = graphene.String()
    temperature = graphene.Float()
    icon = graphene.String()


class HomeDataType(graphene.ObjectType):
    """GraphQL HomeData type"""

    id = graphene.String()
    greeting = graphene.String()
    greeting_prompt = graphene.String()
    time_of_day = graphene.String()
    day_of_week = graphene.String()
    city_name = graphene.String()
    weather = graphene.Field(WeatherType)
    profile_picture = graphene.String()
    user_location = graphene.String()
    allow_location_sharing = graphene.Boolean()
    categories = graphene.List("apps.core.schema.CategoryType")
    editors_pick = graphene.Field("apps.events.types.EventType")
    recommendations = graphene.List("apps.events.types.EventType")
    trending = graphene.List("apps.events.types.EventType")
    upcoming_events = graphene.List("apps.events.types.EventType")
    next_saved_event = graphene.Field("apps.events.types.EventType")
    active_trip = graphene.Field("apps.itinerary.types.TripType")
