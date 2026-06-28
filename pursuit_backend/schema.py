import graphene

from apps.core.schema import CoreQueries
from apps.buckets.schema import BucketsMutations, BucketsQueries
from apps.events.schema import EventsMutations, EventsQueries
from apps.insights.schema import InsightsQueries
from apps.itinerary.schema import ItineraryMutations
from apps.recommendations.schema import RecommendationsQueries
from apps.users.schema import UserMutations, UserQueries
from apps.group_plans.schema import GroupPlansMutations, GroupPlansQueries


class Query(CoreQueries, BucketsQueries, RecommendationsQueries, InsightsQueries, EventsQueries, UserQueries, GroupPlansQueries, graphene.ObjectType):
    """Root Query combining all app queries"""

    # GraphQL requires at least one query field
    health = graphene.String(description="API health check")

    def resolve_health(self, info):
        return "ok"


class Mutation(UserMutations, BucketsMutations, EventsMutations, ItineraryMutations, GroupPlansMutations, graphene.ObjectType):
    """Root Mutation combining all app mutations"""

    pass


schema = graphene.Schema(query=Query, mutation=Mutation)
