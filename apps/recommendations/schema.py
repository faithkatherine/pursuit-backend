import graphene
from graphene_django import DjangoObjectType
from .models import Recommendation


class RecommendationType(DjangoObjectType):
    """GraphQL Recommendation type"""
    
    amount = graphene.Float()
    date = graphene.String()
    image = graphene.String()
    
    class Meta:
        model = Recommendation
        fields = [
            'id', 'title', 'description', 'location', 'estimated_cost',
            'recommendation_type', 'rating', 'created_at'
        ]
    
    def resolve_amount(self, info):
        return float(self.estimated_cost) if self.estimated_cost else None
    
    def resolve_date(self, info):
        return self.date
    
    def resolve_image(self, info):
        return self.get_image_url()


class RecommendationsQueries(graphene.ObjectType):
    """Recommendations GraphQL queries"""
    
    recommendations = graphene.List(RecommendationType)
    
    def resolve_recommendations(self, info):
        return Recommendation.objects.filter(is_active=True, is_featured=True)[:10]
