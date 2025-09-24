from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from apps.core.models import Category
from .models import BucketList, BucketItem
from .serializers import BucketListSerializer, BucketItemSerializer, CategorySerializer


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Category viewset"""
    
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'sort_order']
    ordering = ['sort_order', 'name']


class BucketListViewSet(viewsets.ModelViewSet):
    """Bucket list viewset"""
    
    serializer_class = BucketListSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_default', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return BucketList.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class BucketItemViewSet(viewsets.ModelViewSet):
    """Bucket item viewset"""
    
    serializer_class = BucketItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_completed', 'priority', 'difficulty', 'category']
    search_fields = ['title', 'description', 'location']
    ordering_fields = ['title', 'created_at', 'target_date', 'priority']
    ordering = ['sort_order', '-created_at']
    
    def get_queryset(self):
        return BucketItem.objects.filter(bucket_list__user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark item as completed"""
        item = self.get_object()
        item.is_completed = True
        item.save()
        
        serializer = self.get_serializer(item)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def uncomplete(self, request, pk=None):
        """Mark item as not completed"""
        item = self.get_object()
        item.is_completed = False
        item.completed_date = None
        item.save()
        
        serializer = self.get_serializer(item)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming bucket items"""
        items = self.get_queryset().filter(
            is_completed=False,
            target_date__isnull=False
        ).order_by('target_date')[:5]
        
        serializer = self.get_serializer(items, many=True)
        return Response(serializer.data)
