import graphene

from apps.events.types import EventType

from .services import get_recommended_events


class RecommendationsQueries(graphene.ObjectType):
    """Recommendations GraphQL queries"""

    get_recommendations = graphene.List(
        EventType, offset=graphene.Int(), limit=graphene.Int()
    )

    def resolve_get_recommendations(self, info, offset=0, limit=10):
        user = info.context.user
        if not user.is_authenticated:
            return []

        results = get_recommended_events(user, offset, limit)
        events = []
        for event, reason, source in results:
            event._reason = reason
            event._source = source
            event._is_saved = False  # excluded saved events already
            events.append(event)
        return events
