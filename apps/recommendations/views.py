from rest_framework import viewsets, permissions
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from .models import Recommendation


class RecommendationViewSet(viewsets.ReadOnlyModelViewSet):
    """Recommendation viewset"""
    
    queryset = Recommendation.objects.filter(is_active=True)
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['recommendation_type', 'category', 'location']
    search_fields = ['title', 'description', 'location']
    ordering_fields = ['title', 'created_at', 'popularity_score', 'rating']
    ordering = ['-popularity_score', '-created_at']
