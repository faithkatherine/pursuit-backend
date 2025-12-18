import graphene
from graphene_django import DjangoObjectType

from apps.users.schema import UserQueries, UserMutations
from apps.buckets.schema import BucketsQueries, BucketsMutations
from apps.recommendations.schema import RecommendationsQueries
from apps.insights.schema import InsightsQueries


class Query(
    # BucketsQueries,
    # RecommendationsQueries,
    # InsightsQueries,
    UserQueries,
    graphene.ObjectType
):
    """Root Query combining all app queries"""
    # GraphQL requires at least one query field
    health = graphene.String(description="API health check")

    def resolve_health(self, info):
        return "ok"


class Mutation(
    UserMutations,
    # BucketsMutations,
    graphene.ObjectType
):
    """Root Mutation combining all app mutations"""
    pass


schema = graphene.Schema(query=Query, mutation=Mutation)
