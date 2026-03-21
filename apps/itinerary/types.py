import graphene
from graphene_django import DjangoObjectType

from .models import Trip


class TripType(DjangoObjectType):
    """Trip GraphQL type with cover_image fallback chain."""

    cover_image = graphene.String()
    event_count = graphene.Int()

    class Meta:
        model = Trip
        fields = (
            "id",
            "name",
            "destination",
            "start_date",
            "end_date",
            "image",
            "events",
            "created_at",
            "updated_at",
        )

    def resolve_cover_image(self, info):
        # 1. User-provided image
        if self.image:
            return self.image
        # 2. First linked event's image (soonest by date)
        first_event = self.events.filter(image__isnull=False).exclude(image="").order_by("date").first()
        if first_event:
            return first_event.image
        # 3. None — frontend renders gradient fallback
        return None

    def resolve_event_count(self, info):
        return self.events.count()
