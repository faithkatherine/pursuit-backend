from rest_framework import serializers
from apps.core.models import Category
from .models import BucketList, BucketItem, BucketItemPhoto, BucketItemProgress


class CategorySerializer(serializers.ModelSerializer):
    """Category serializer"""
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'emoji', 'description', 'color']


class BucketItemSerializer(serializers.ModelSerializer):
    """Bucket item serializer"""
    
    category = CategorySerializer(read_only=True)
    category_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    image = serializers.SerializerMethodField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True, source='estimated_cost')
    completed = serializers.BooleanField(source='is_completed', read_only=True)
    
    class Meta:
        model = BucketItem
        fields = [
            'id', 'title', 'description', 'notes', 'image', 'location',
            'estimated_cost', 'amount', 'currency', 'target_date', 'priority',
            'difficulty', 'is_completed', 'completed', 'completed_date', 'progress_percentage',
            'is_public', 'likes_count', 'category', 'category_id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'likes_count', 'completed_date', 'created_at', 'updated_at']
    
    def get_image(self, obj):
        return obj.get_image_url()
    
    def create(self, validated_data):
        category_id = validated_data.pop('category_id', None)
        if category_id:
            validated_data['category_id'] = category_id
        
        # Get the user's default bucket list
        user = self.context['request'].user
        bucket_list, created = BucketList.objects.get_or_create(
            user=user,
            is_default=True,
            defaults={'name': 'My Bucket List'}
        )
        validated_data['bucket_list'] = bucket_list
        
        return super().create(validated_data)


class BucketListSerializer(serializers.ModelSerializer):
    """Bucket list serializer"""
    
    items = BucketItemSerializer(many=True, read_only=True)
    items_count = serializers.SerializerMethodField()
    completed_count = serializers.SerializerMethodField()
    
    class Meta:
        model = BucketList
        fields = [
            'id', 'name', 'description', 'is_default', 'is_active',
            'items', 'items_count', 'completed_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_items_count(self, obj):
        return obj.items.count()
    
    def get_completed_count(self, obj):
        return obj.items.filter(is_completed=True).count()


class BucketItemProgressSerializer(serializers.ModelSerializer):
    """Bucket item progress serializer"""
    
    class Meta:
        model = BucketItemProgress
        fields = [
            'id', 'title', 'description', 'progress_percentage', 'image', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
