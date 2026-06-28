import graphene
from graphql import GraphQLError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .models import (
    GroupPlan,
    GroupPlanEvent,
    VoteInvitation,
    IndividualVoterSession,
    Vote
)
from .types import (
    GroupPlanType,
    GroupPlanEventType,
    VoteInvitationType,
    IndividualVoterSessionType,
    VoteType,
    VoteDirectionEnum
)
from apps.events.models import Event


# Mutations

class CreateGroupPlan(graphene.Mutation):
    """Create a new group plan"""

    class Arguments:
        name = graphene.String()

    group_plan = graphene.Field(GroupPlanType)

    def mutate(self, info, name=None):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        # Create plan
        plan = GroupPlan.objects.create(
            creator=user,
            name=name or '',
            status='DRAFT'
        )

        # Auto-create first invitation for creator
        VoteInvitation.objects.create(
            group_plan=plan,
            created_by=user,
            is_active=True
        )

        return CreateGroupPlan(group_plan=plan)


class AddEventToBucket(graphene.Mutation):
    """Add an event to the group plan bucket"""

    class Arguments:
        group_plan_id = graphene.ID(required=True)
        event_id = graphene.ID(required=True)

    group_plan_event = graphene.Field(GroupPlanEventType)

    def mutate(self, info, group_plan_id, event_id):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        try:
            plan = GroupPlan.objects.get(pk=group_plan_id)
        except GroupPlan.DoesNotExist:
            raise GraphQLError("Group plan not found")

        # Only creator can add events
        if plan.creator != user:
            raise GraphQLError("Only the creator can add events to this plan")

        try:
            event = Event.objects.get(pk=event_id, is_active=True)
        except Event.DoesNotExist:
            raise GraphQLError("Event not found")

        # Check for duplicate
        if GroupPlanEvent.objects.filter(group_plan=plan, event=event).exists():
            raise GraphQLError("Event already in bucket")

        # Get max ordering + 1
        max_ordering = plan.bucket_events.aggregate(
            max_ord=Max('ordering')
        )['max_ord'] or 0

        bucket_event = GroupPlanEvent.objects.create(
            group_plan=plan,
            event=event,
            added_by=user,
            ordering=max_ordering + 1
        )

        return AddEventToBucket(group_plan_event=bucket_event)


class RemoveEventFromBucket(graphene.Mutation):
    """Remove an event from the bucket"""

    class Arguments:
        group_plan_event_id = graphene.ID(required=True)

    success = graphene.Boolean()

    def mutate(self, info, group_plan_event_id):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        try:
            bucket_event = GroupPlanEvent.objects.select_related('group_plan').get(
                pk=group_plan_event_id
            )
        except GroupPlanEvent.DoesNotExist:
            raise GraphQLError("Bucket event not found")

        # Only creator can remove
        if bucket_event.group_plan.creator != user:
            raise GraphQLError("Only the creator can remove events")

        bucket_event.delete()
        return RemoveEventFromBucket(success=True)


class ReorderBucketEvents(graphene.Mutation):
    """Reorder events in the bucket"""

    class Arguments:
        group_plan_id = graphene.ID(required=True)
        ordered_ids = graphene.List(graphene.NonNull(graphene.ID), required=True)

    bucket_events = graphene.List(graphene.NonNull(GroupPlanEventType))

    def mutate(self, info, group_plan_id, ordered_ids):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        try:
            plan = GroupPlan.objects.get(pk=group_plan_id)
        except GroupPlan.DoesNotExist:
            raise GraphQLError("Group plan not found")

        if plan.creator != user:
            raise GraphQLError("Only the creator can reorder events")

        # Update ordering for each ID
        with transaction.atomic():
            for idx, event_id in enumerate(ordered_ids):
                GroupPlanEvent.objects.filter(
                    pk=event_id,
                    group_plan=plan
                ).update(ordering=idx)

        # Return reordered events
        events = list(plan.bucket_events.order_by('ordering'))
        return ReorderBucketEvents(bucket_events=events)


class UpdateGroupPlanName(graphene.Mutation):
    """Update the group plan name"""

    class Arguments:
        group_plan_id = graphene.ID(required=True)
        name = graphene.String(required=True)

    group_plan = graphene.Field(GroupPlanType)

    def mutate(self, info, group_plan_id, name):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        try:
            plan = GroupPlan.objects.get(pk=group_plan_id)
        except GroupPlan.DoesNotExist:
            raise GraphQLError("Group plan not found")

        if plan.creator != user:
            raise GraphQLError("Only the creator can rename the plan")

        plan.name = name
        plan.save(update_fields=['name', 'updated_at'])
        return UpdateGroupPlanName(group_plan=plan)


class OpenGroupPlanForVoting(graphene.Mutation):
    """Open the plan for voting"""

    class Arguments:
        group_plan_id = graphene.ID(required=True)

    group_plan = graphene.Field(GroupPlanType)

    def mutate(self, info, group_plan_id):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        try:
            plan = GroupPlan.objects.get(pk=group_plan_id)
        except GroupPlan.DoesNotExist:
            raise GraphQLError("Group plan not found")

        if plan.creator != user:
            raise GraphQLError("Only the creator can open the plan")

        plan.status = 'OPEN'
        plan.save(update_fields=['status', 'updated_at'])
        return OpenGroupPlanForVoting(group_plan=plan)


class CreateVoterSession(graphene.Mutation):
    """Create a new voter session"""

    class Arguments:
        share_token = graphene.String(required=True)
        voter_name = graphene.String()

    voter_session = graphene.Field(IndividualVoterSessionType)

    def mutate(self, info, share_token, voter_name=None):
        try:
            invitation = VoteInvitation.objects.select_related('group_plan').get(
                share_token=share_token,
                is_active=True
            )
        except VoteInvitation.DoesNotExist:
            raise GraphQLError("Invalid or inactive invitation")

        # Create session
        session = IndividualVoterSession.objects.create(
            invitation=invitation,
            voter_name=voter_name or '',
            registered_user=info.context.user if info.context.user.is_authenticated else None
        )

        return CreateVoterSession(voter_session=session)


class CastVote(graphene.Mutation):
    """Cast a vote on a group plan event"""

    class Arguments:
        group_plan_event_id = graphene.ID(required=True)
        session_token = graphene.String(required=True)
        direction = VoteDirectionEnum(required=True)

    vote = graphene.Field(VoteType)

    def mutate(self, info, group_plan_event_id, session_token, direction):
        # Validate session
        try:
            voter_session = IndividualVoterSession.objects.get(session_token=session_token)
        except IndividualVoterSession.DoesNotExist:
            raise GraphQLError("Invalid session token")

        # Validate event
        try:
            group_plan_event = GroupPlanEvent.objects.get(pk=group_plan_event_id)
        except GroupPlanEvent.DoesNotExist:
            raise GraphQLError("Group plan event not found")

        # Upsert vote
        # Convert enum to string value if needed
        direction_value = direction.value if hasattr(direction, 'value') else direction
        vote, created = Vote.objects.update_or_create(
            group_plan_event=group_plan_event,
            voter_session=voter_session,
            defaults={'direction': direction_value}
        )

        # Update last_seen_at
        voter_session.last_seen_at = timezone.now()
        voter_session.save(update_fields=['last_seen_at'])

        return CastVote(vote=vote)


class CloseGroupPlan(graphene.Mutation):
    """Close the group plan"""

    class Arguments:
        group_plan_id = graphene.ID(required=True)

    group_plan = graphene.Field(GroupPlanType)

    def mutate(self, info, group_plan_id):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        try:
            plan = GroupPlan.objects.get(pk=group_plan_id)
        except GroupPlan.DoesNotExist:
            raise GraphQLError("Group plan not found")

        if plan.creator != user:
            raise GraphQLError("Only the creator can close the plan")

        plan.status = 'CLOSED'
        plan.save(update_fields=['status', 'updated_at'])
        return CloseGroupPlan(group_plan=plan)


# Queries

class GroupPlansQueries(graphene.ObjectType):
    """Group Plans queries"""

    group_plan = graphene.Field(
        GroupPlanType,
        id=graphene.ID(required=True)
    )
    group_plan_by_share_token = graphene.Field(
        GroupPlanType,
        share_token=graphene.String(required=True)
    )
    my_group_plans = graphene.List(graphene.NonNull(GroupPlanType))
    event_suggestions_for_group_plan = graphene.List(
        'apps.events.types.EventType',
        group_plan_id=graphene.ID(required=True),
        date=graphene.Date()
    )

    def resolve_group_plan(self, info, id):
        """Get group plan by ID"""
        try:
            return GroupPlan.objects.prefetch_related(
                'bucket_events__event',
                'invitations'
            ).get(pk=id)
        except GroupPlan.DoesNotExist:
            raise GraphQLError("Group plan not found")

    def resolve_group_plan_by_share_token(self, info, share_token):
        """Get group plan by share token"""
        try:
            invitation = VoteInvitation.objects.select_related('group_plan').get(
                share_token=share_token,
                is_active=True
            )
            return invitation.group_plan
        except VoteInvitation.DoesNotExist:
            raise GraphQLError("Invalid or inactive invitation")

    def resolve_my_group_plans(self, info):
        """Get user's created group plans"""
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        return GroupPlan.objects.filter(creator=user).prefetch_related(
            'bucket_events',
            'invitations'
        ).order_by('-created_at')

    def resolve_event_suggestions_for_group_plan(self, info, group_plan_id, date=None):
        """Get event suggestions for a group plan"""
        from apps.events.models import Event, UserEvents

        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        try:
            plan = GroupPlan.objects.get(pk=group_plan_id)
        except GroupPlan.DoesNotExist:
            raise GraphQLError("Group plan not found")

        # Get already added event IDs
        existing_event_ids = set(
            plan.bucket_events.values_list('event_id', flat=True)
        )

        suggestions = []

        # 1. User's saved events
        saved_events_qs = Event.objects.filter(
            user_interactions__user=user,
            is_active=True
        ).exclude(pk__in=existing_event_ids)

        if date:
            saved_events_qs = saved_events_qs.filter(date__date=date)

        suggestions.extend(list(saved_events_qs[:3]))

        # 2. Trending events (high going_count)
        if len(suggestions) < 7:
            trending_qs = Event.objects.filter(
                is_active=True
            ).exclude(pk__in=existing_event_ids).exclude(
                pk__in=[e.pk for e in suggestions]
            ).order_by('-going_count')

            if date:
                trending_qs = trending_qs.filter(date__date=date)

            suggestions.extend(list(trending_qs[:(7 - len(suggestions))]))

        return suggestions[:7]


# Mutations container

class GroupPlansMutations(graphene.ObjectType):
    """Group Plans mutations"""

    create_group_plan = CreateGroupPlan.Field()
    add_event_to_bucket = AddEventToBucket.Field()
    remove_event_from_bucket = RemoveEventFromBucket.Field()
    reorder_bucket_events = ReorderBucketEvents.Field()
    update_group_plan_name = UpdateGroupPlanName.Field()
    open_group_plan_for_voting = OpenGroupPlanForVoting.Field()
    create_voter_session = CreateVoterSession.Field()
    cast_vote = CastVote.Field()
    close_group_plan = CloseGroupPlan.Field()
