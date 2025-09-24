from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BucketListViewSet, BucketItemViewSet, CategoryViewSet

router = DefaultRouter()
router.register(r'lists', BucketListViewSet, basename='bucket-lists')
router.register(r'items', BucketItemViewSet, basename='bucket-items')
router.register(r'categories', CategoryViewSet, basename='categories')

urlpatterns = [
    path('', include(router.urls)),
]
