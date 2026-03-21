import graphene

from apps.buckets.schema import BucketsMutations, BucketsQueries
from apps.events.schema import EventsMutations, EventsQueries
from apps.insights.schema import InsightsQueries
from apps.recommendations.schema import RecommendationsQueries
from apps.itinerary.schema import ItineraryMutations
from apps.users.schema import UserMutations, UserQueries


class Query(BucketsQueries, RecommendationsQueries, InsightsQueries, EventsQueries, UserQueries, graphene.ObjectType):
    """Root Query combining all app queries"""

    # GraphQL requires at least one query field
    health = graphene.String(description="API health check")

    def resolve_health(self, info):
        return "ok"


class Mutation(UserMutations, BucketsMutations, EventsMutations, ItineraryMutations, graphene.ObjectType):
    """Root Mutation combining all app mutations"""

    pass


schema = graphene.Schema(query=Query, mutation=Mutation)
