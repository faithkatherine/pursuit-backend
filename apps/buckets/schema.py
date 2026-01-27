import graphene
from graphene_django import DjangoObjectType
from apps.core.models import Category
from .models import BucketList, BucketItem



class CategoryType(DjangoObjectType):
    """GraphQL Category type"""
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'emoji', 'description', 'color']


class BucketItemType(DjangoObjectType):
    """GraphQL BucketItem type"""

    amount = graphene.Float()
    completed = graphene.Boolean()
    image = graphene.String()
    category_id = graphene.String()

    class Meta:
        model = BucketItem
        fields = [
            'id', 'title', 'description', 'location', 'estimated_cost',
            'priority', 'difficulty', 'is_completed', 'progress_percentage',
            'category', 'created_at', 'updated_at'
        ]

    def resolve_amount(self, info):
        return float(self.estimated_cost) if self.estimated_cost else None

    def resolve_completed(self, info):
        return self.is_completed

    def resolve_image(self, info):
        return self.get_image_url()

    def resolve_category_id(self, info):
        return str(self.category_id) if self.category_id else None


class BucketListType(DjangoObjectType):
    """GraphQL BucketList type"""
    
    class Meta:
        model = BucketList
        fields = ['id', 'name', 'description', 'is_default', 'created_at']


# Mutations
class AddBucketCategory(graphene.Mutation):
    """Add bucket category mutation"""
    
    class Arguments:
        name = graphene.String(required=True)
        emoji = graphene.String()
    
    category = graphene.Field(CategoryType)
    
    def mutate(self, info, name, emoji=''):
        if not info.context.user.is_authenticated:
            raise Exception('Authentication required')
        
        category = Category.objects.create(
            name=name,
            emoji=emoji
        )
        
        return AddBucketCategory(category=category)


class AddBucketItem(graphene.Mutation):
    """Add bucket item mutation"""
    
    class Arguments:
        title = graphene.String(required=True)
        description = graphene.String()
        location = graphene.String()
        estimated_cost = graphene.Float()
        category_id = graphene.String()
    
    bucket_item = graphene.Field(BucketItemType)
    
    def mutate(self, info, title, description='', location='', estimated_cost=None, category_id=None):
        user = info.context.user
        if not user.is_authenticated:
            raise Exception('Authentication required')
        
        # Get user's default bucket list
        bucket_list, created = BucketList.objects.get_or_create(
            user=user,
            is_default=True,
            defaults={'name': 'My Bucket List'}
        )
        
        category = None
        if category_id:
            try:
                category = Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                pass
        
        bucket_item = BucketItem.objects.create(
            bucket_list=bucket_list,
            title=title,
            description=description,
            location=location,
            estimated_cost=estimated_cost,
            category=category
        )
        
        return AddBucketItem(bucket_item=bucket_item)


# Queries
class BucketsQueries(graphene.ObjectType):
    """Buckets GraphQL queries"""

    get_bucket_categories = graphene.List(CategoryType)
    get_bucket_items = graphene.List(BucketItemType, category_id=graphene.String())

    def resolve_get_bucket_categories(self, info):
        return Category.objects.filter(is_active=True)

    def resolve_get_bucket_items(self, info, category_id=None):
        user = info.context.user
        if user.is_authenticated:
            items = BucketItem.objects.filter(bucket_list__user=user)
            if category_id:
                items = items.filter(category_id=category_id)
            return items
        return []


# Mutations
class BucketsMutations(graphene.ObjectType):
    """Buckets GraphQL mutations"""
    
    add_bucket_category = AddBucketCategory.Field()
    add_bucket_item = AddBucketItem.Field()
