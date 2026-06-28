import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from apps.events.models import Event


class GroupPlanQuerySet(models.QuerySet):
    """Custom queryset for GroupPlan"""

    def for_user(self, user):
        """Return plans where user is creator"""
        return self.filter(creator=user).order_by('-created_at')


class GroupPlanManager(models.Manager):
    """Custom manager for GroupPlan"""

    def get_queryset(self):
        return GroupPlanQuerySet(self.model, using=self._db)

    def for_user(self, user):
        return self.get_queryset().for_user(user)


class GroupPlan(models.Model):
    """Group plan for collaborative event selection"""

    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('OPEN', 'Open'),
        ('CLOSED', 'Closed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_group_plans'
    )
    name = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DRAFT')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = GroupPlanManager()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        """
        Returns name if set, else auto-generated:
        "{creator.first_name}'s {dominant_category} Picks · {Mon DD}"
        """
        if self.name:
            return self.name

        # Get dominant category from bucket events
        bucket_events = self.bucket_events.prefetch_related('event__category').all()
        if not bucket_events:
            # No events yet
            date_str = self.created_at.strftime('%b %d')
            return f"{self.creator.first_name}'s Picks · {date_str}"

        # Find most common category
        categories = [be.event.category.all()[0].name for be in bucket_events if be.event.category.exists()]
        if categories:
            # Get most common
            dominant_category = max(set(categories), key=categories.count)
        else:
            dominant_category = None

        date_str = self.created_at.strftime('%b %d')
        if dominant_category:
            return f"{self.creator.first_name}'s {dominant_category} Picks · {date_str}"
        return f"{self.creator.first_name}'s Picks · {date_str}"


class GroupPlanEventQuerySet(models.QuerySet):
    """Custom queryset for GroupPlanEvent"""

    def with_vote_counts(self):
        """Annotate each item with interested_count and skip_count"""
        from django.db.models import Count, Q
        return self.annotate(
            interested_count=Count(
                'votes',
                filter=Q(votes__direction='INTERESTED')
            ),
            skip_count=Count(
                'votes',
                filter=Q(votes__direction='SKIP')
            )
        )


class GroupPlanEventManager(models.Manager):
    """Custom manager for GroupPlanEvent"""

    def get_queryset(self):
        return GroupPlanEventQuerySet(self.model, using=self._db)

    def with_vote_counts(self):
        return self.get_queryset().with_vote_counts()


class GroupPlanEvent(models.Model):
    """Event in a group plan bucket"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group_plan = models.ForeignKey(
        GroupPlan,
        on_delete=models.CASCADE,
        related_name='bucket_events'
    )
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    added_at = models.DateTimeField(auto_now_add=True)
    ordering = models.PositiveIntegerField(default=0)

    objects = GroupPlanEventManager()

    class Meta:
        unique_together = ('group_plan', 'event')
        ordering = ['ordering', 'added_at']

    def __str__(self):
        return f"{self.event.name} in {self.group_plan.display_name}"


class VoteInvitation(models.Model):
    """Invitation to vote on a group plan"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group_plan = models.ForeignKey(
        GroupPlan,
        on_delete=models.CASCADE,
        related_name='invitations'
    )
    share_token = models.UUIDField(unique=True, default=uuid.uuid4)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Invitation for {self.group_plan.display_name}"


class IndividualVoterSessionQuerySet(models.QuerySet):
    """Custom queryset for IndividualVoterSession"""

    def for_group_plan(self, group_plan):
        """Returns all sessions for a given group plan"""
        return self.filter(
            invitation__group_plan=group_plan
        )


class IndividualVoterSessionManager(models.Manager):
    """Custom manager for IndividualVoterSession"""

    def get_queryset(self):
        return IndividualVoterSessionQuerySet(self.model, using=self._db)

    def for_group_plan(self, group_plan):
        return self.get_queryset().for_group_plan(group_plan)


# Color palette for voter avatars
VOTER_COLORS = ['purple', 'pink', 'teal', 'amber', 'coral']


class IndividualVoterSession(models.Model):
    """Anonymous or authenticated voter session"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invitation = models.ForeignKey(
        VoteInvitation,
        on_delete=models.CASCADE,
        related_name='voter_sessions'
    )
    session_token = models.UUIDField(unique=True, default=uuid.uuid4)
    voter_name = models.CharField(max_length=60, blank=True)
    display_initial = models.CharField(max_length=1)
    display_color = models.CharField(max_length=20)
    registered_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    objects = IndividualVoterSessionManager()

    def __str__(self):
        if self.voter_name:
            return f"{self.voter_name} ({self.display_initial})"
        return f"Voter {self.display_initial}"

    def save(self, *args, **kwargs):
        # Auto-assign display_initial and display_color if not set
        if not self.display_initial or not self.display_color:
            # Count existing sessions for this invitation to assign initial and color
            session_count = IndividualVoterSession.objects.filter(
                invitation=self.invitation
            ).exclude(pk=self.pk).count()

            if not self.display_initial:
                if self.voter_name:
                    self.display_initial = self.voter_name[0].upper()
                else:
                    # Assign letter A, B, C, etc.
                    self.display_initial = chr(65 + (session_count % 26))

            if not self.display_color:
                # Cycle through color palette
                self.display_color = VOTER_COLORS[session_count % len(VOTER_COLORS)]

        super().save(*args, **kwargs)


class Vote(models.Model):
    """Vote cast on a group plan event"""

    DIRECTION_CHOICES = [
        ('INTERESTED', 'Interested'),
        ('SKIP', 'Skip'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group_plan_event = models.ForeignKey(
        GroupPlanEvent,
        on_delete=models.CASCADE,
        related_name='votes'
    )
    voter_session = models.ForeignKey(
        IndividualVoterSession,
        on_delete=models.CASCADE,
        related_name='votes'
    )
    direction = models.CharField(max_length=15, choices=DIRECTION_CHOICES)
    cast_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('group_plan_event', 'voter_session')

    def __str__(self):
        return f"{self.voter_session} voted {self.direction} on {self.group_plan_event.event.name}"
