import graphene
from graphene_django import DjangoObjectType
from django.db.models import Count, Q

from .models import (
    GroupPlan,
    GroupPlanEvent,
    VoteInvitation,
    IndividualVoterSession,
    Vote
)
from apps.events.types import EventType
from apps.users.types import UserType


class GroupPlanType(DjangoObjectType):
    """GraphQL type for GroupPlan"""

    display_name = graphene.String()
    my_voter_session = graphene.Field(lambda: IndividualVoterSessionType)

    class Meta:
        model = GroupPlan
        fields = (
            'id',
            'creator',
            'name',
            'status',
            'bucket_events',
            'invitations',
            'created_at',
            'updated_at',
        )

    def resolve_display_name(self, info):
        return self.display_name

    def resolve_my_voter_session(self, info):
        """Returns the caller's session for this plan if one exists"""
        # Check for session token in custom header
        session_token = info.context.META.get('HTTP_X_VOTER_SESSION_TOKEN')
        if not session_token:
            return None

        # Find session for this group plan's invitations
        try:
            invitation = self.invitations.filter(is_active=True).first()
            if not invitation:
                return None

            return IndividualVoterSession.objects.get(
                invitation=invitation,
                session_token=session_token
            )
        except IndividualVoterSession.DoesNotExist:
            return None


class VoterInfoType(graphene.ObjectType):
    """Info about a voter who voted INTERESTED on an event"""

    display_initial = graphene.String(required=True)
    display_color = graphene.String(required=True)
    voter_name = graphene.String()
    profile_picture = graphene.String()

    @staticmethod
    def from_session(session):
        return VoterInfoType(
            display_initial=session.display_initial,
            display_color=session.display_color,
            voter_name=session.voter_name or None,
            profile_picture=session.registered_user.profile_picture if session.registered_user else None
        )


class GroupPlanEventType(DjangoObjectType):
    """GraphQL type for GroupPlanEvent"""

    interested_count = graphene.Int(required=True)
    voters = graphene.List(graphene.NonNull(VoterInfoType), required=True)

    class Meta:
        model = GroupPlanEvent
        fields = (
            'id',
            'event',
            'added_by',
            'ordering',
            'added_at',
        )

    def resolve_interested_count(self, info):
        # Use annotation if available, otherwise count
        if hasattr(self, 'interested_count'):
            return self.interested_count
        return self.votes.filter(direction='INTERESTED').count()

    def resolve_voters(self, info):
        """Only INTERESTED voters for results display"""
        interested_votes = self.votes.filter(direction='INTERESTED').select_related(
            'voter_session',
            'voter_session__registered_user'
        )
        return [
            VoterInfoType.from_session(vote.voter_session)
            for vote in interested_votes
        ]


class VoteInvitationType(DjangoObjectType):
    """GraphQL type for VoteInvitation"""

    share_token = graphene.String(required=True)

    class Meta:
        model = VoteInvitation
        fields = (
            'id',
            'share_token',
            'is_active',
            'created_at',
        )

    def resolve_share_token(self, info):
        return str(self.share_token)


class IndividualVoterSessionType(DjangoObjectType):
    """GraphQL type for IndividualVoterSession"""

    session_token = graphene.String(required=True)
    has_completed_stack = graphene.Boolean(required=True)
    my_votes = graphene.List(graphene.NonNull(graphene.ID), required=True)

    class Meta:
        model = IndividualVoterSession
        fields = (
            'id',
            'session_token',
            'display_initial',
            'display_color',
            'voter_name',
        )

    def resolve_session_token(self, info):
        return str(self.session_token)

    def resolve_has_completed_stack(self, info):
        """True if votes+skips count equals group plan bucket size"""
        group_plan = self.invitation.group_plan
        bucket_size = group_plan.bucket_events.count()
        vote_count = self.votes.count()
        return vote_count >= bucket_size

    def resolve_my_votes(self, info):
        """List of GroupPlanEvent IDs this session voted INTERESTED on"""
        return [
            str(vote.group_plan_event_id)
            for vote in self.votes.filter(direction='INTERESTED')
        ]


class VoteType(DjangoObjectType):
    """GraphQL type for Vote"""

    class Meta:
        model = Vote
        fields = (
            'id',
            'group_plan_event',
            'voter_session',
            'direction',
            'cast_at',
        )


# Enum for vote direction
class VoteDirectionEnum(graphene.Enum):
    INTERESTED = 'INTERESTED'
    SKIP = 'SKIP'
