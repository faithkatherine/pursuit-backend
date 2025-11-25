import graphene
from graphene_django import DjangoObjectType
from users.schema import AccountsMutations, AccountsQueries
from apps.buckets.schema import BucketsMutations, BucketsQueries
from apps.recommendations.schema import RecommendationsQueries
from apps.insights.schema import InsightsQueries


class Query(
    AccountsQueries,
    BucketsQueries,
    RecommendationsQueries,
    InsightsQueries,
    graphene.ObjectType
):
    """Root Query combining all app queries"""
    pass


class Mutation(
    AccountsMutations,
    BucketsMutations,
    graphene.ObjectType
):
    """Root Mutation combining all app mutations"""
    pass


schema = graphene.Schema(query=Query, mutation=Mutation)
