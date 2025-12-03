import graphene
from graphene_django import DjangoObjectType

from apps.users.schema import UsersMutations


class Query(graphene.ObjectType):
    """Root Query combining all app queries"""
    # GraphQL requires at least one query field
    health = graphene.String(description="API health check")

    def resolve_health(self, info):
        return "ok"


class Mutation(  
    UsersMutations,
    graphene.ObjectType
):
    """Root Mutation combining all app mutations"""
    pass


schema = graphene.Schema(query=Query, mutation=Mutation)
