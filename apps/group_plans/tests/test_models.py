import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone
from datetime import datetime
from apps.events.models import Event
from apps.core.models import Category
from apps.group_plans.models import (
    GroupPlan,
    GroupPlanEvent,
    VoteInvitation,
    IndividualVoterSession,
    Vote,
    VOTER_COLORS
)

User = get_user_model()


@pytest.mark.django_db
class TestGroupPlan:
    """Tests for GroupPlan model"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='testpass123',
            first_name='Test'
        )
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category'
        )

    def test_display_name_with_custom_name(self):
        """Test display_name property when name is set"""
        plan = GroupPlan.objects.create(
            creator=self.user,
            name='My Custom Plan'
        )
        assert plan.display_name == 'My Custom Plan'

    def test_display_name_without_name_no_events(self):
        """Test display_name property without name and no events"""
        plan = GroupPlan.objects.create(
            creator=self.user,
            name=''
        )
        # Format: "{first_name}'s Picks · {date}"
        assert "Test's Picks" in plan.display_name
        # Should include date
        today = timezone.now().strftime('%b %d')
        assert today in plan.display_name

    def test_display_name_with_dominant_category(self):
        """Test display_name with events showing dominant category"""
        plan = GroupPlan.objects.create(
            creator=self.user,
            name=''
        )

        category1 = Category.objects.create(name='Music', slug='music')
        category2 = Category.objects.create(name='Food', slug='food')

        # Add 3 music events and 1 food event
        for i in range(3):
            event = Event.objects.create(
                name=f'Music Event {i}',
                date=timezone.now(),
                is_active=True
            )
            event.category.set([category1])
            GroupPlanEvent.objects.create(
                group_plan=plan,
                event=event,
                added_by=self.user
            )

        event = Event.objects.create(
            name='Food Event',
            date=timezone.now(),
            is_active=True
        )
        event.category.set([category2])
        GroupPlanEvent.objects.create(
            group_plan=plan,
            event=event,
            added_by=self.user
        )

        # Should contain dominant category name
        assert 'Music' in plan.display_name


@pytest.mark.django_db
class TestGroupPlanEvent:
    """Tests for GroupPlanEvent model"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='testpass123',
            first_name='Test'
        )
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category'
        )
        self.plan = GroupPlan.objects.create(creator=self.user)
        from django.utils import timezone
        self.event = Event.objects.create(
            name='Test Event',
            date=timezone.now(),
            is_active=True
        )
        self.event.category.set([self.category])

    def test_with_vote_counts_annotation(self):
        """Test with_vote_counts() manager method"""
        bucket_event = GroupPlanEvent.objects.create(
            group_plan=self.plan,
            event=self.event,
            added_by=self.user
        )

        invitation = VoteInvitation.objects.create(
            group_plan=self.plan,
            created_by=self.user,
            is_active=True
        )

        # Create 3 sessions with different votes
        session1 = IndividualVoterSession.objects.create(
            invitation=invitation,
            voter_name='Voter 1'
        )
        session2 = IndividualVoterSession.objects.create(
            invitation=invitation,
            voter_name='Voter 2'
        )
        session3 = IndividualVoterSession.objects.create(
            invitation=invitation,
            voter_name='Voter 3'
        )

        # 2 interested, 1 skip
        Vote.objects.create(
            group_plan_event=bucket_event,
            voter_session=session1,
            direction='INTERESTED'
        )
        Vote.objects.create(
            group_plan_event=bucket_event,
            voter_session=session2,
            direction='INTERESTED'
        )
        Vote.objects.create(
            group_plan_event=bucket_event,
            voter_session=session3,
            direction='SKIP'
        )

        # Use manager method
        annotated = GroupPlanEvent.objects.with_vote_counts().get(pk=bucket_event.pk)
        assert annotated.interested_count == 2
        assert annotated.skip_count == 1

    def test_unique_constraint(self):
        """Test unique together constraint for group_plan and event"""
        GroupPlanEvent.objects.create(
            group_plan=self.plan,
            event=self.event,
            added_by=self.user
        )

        # Try to add same event again - should raise IntegrityError
        with pytest.raises(IntegrityError):
            GroupPlanEvent.objects.create(
                group_plan=self.plan,
                event=self.event,
                added_by=self.user
            )


@pytest.mark.django_db
class TestIndividualVoterSession:
    """Tests for IndividualVoterSession model"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='testpass123',
            first_name='Test'
        )
        self.plan = GroupPlan.objects.create(creator=self.user)
        self.invitation = VoteInvitation.objects.create(
            group_plan=self.plan,
            created_by=self.user,
            is_active=True
        )

    def test_auto_assign_display_initial_from_name(self):
        """Test auto-assignment of display_initial from voter_name"""
        session = IndividualVoterSession.objects.create(
            invitation=self.invitation,
            voter_name='Sarah'
        )
        assert session.display_initial == 'S'

    def test_auto_assign_display_initial_sequential(self):
        """Test auto-assignment of sequential letters when no name"""
        session1 = IndividualVoterSession.objects.create(
            invitation=self.invitation,
            voter_name=''
        )
        session2 = IndividualVoterSession.objects.create(
            invitation=self.invitation,
            voter_name=''
        )
        session3 = IndividualVoterSession.objects.create(
            invitation=self.invitation,
            voter_name=''
        )

        assert session1.display_initial == 'A'
        assert session2.display_initial == 'B'
        assert session3.display_initial == 'C'

    def test_auto_assign_display_color_cycles(self):
        """Test display_color cycles through palette"""
        sessions = []
        num_colors = len(VOTER_COLORS)

        # Create more sessions than colors to test cycling
        for i in range(num_colors + 2):
            session = IndividualVoterSession.objects.create(
                invitation=self.invitation,
                voter_name=f'Voter {i}'
            )
            sessions.append(session)

        # First N sessions should match colors in order
        for i in range(num_colors):
            assert sessions[i].display_color == VOTER_COLORS[i]

        # Should cycle back to first color
        assert sessions[num_colors].display_color == VOTER_COLORS[0]
        assert sessions[num_colors + 1].display_color == VOTER_COLORS[1]

    def test_for_group_plan_manager_method(self):
        """Test for_group_plan() manager method returns correct sessions"""
        # Create another plan
        plan2 = GroupPlan.objects.create(creator=self.user)
        invitation2 = VoteInvitation.objects.create(
            group_plan=plan2,
            created_by=self.user,
            is_active=True
        )

        # Create sessions for both plans
        session1 = IndividualVoterSession.objects.create(
            invitation=self.invitation,
            voter_name='Plan 1 Voter'
        )
        session2 = IndividualVoterSession.objects.create(
            invitation=invitation2,
            voter_name='Plan 2 Voter'
        )

        # Get sessions for plan1
        plan1_sessions = IndividualVoterSession.objects.for_group_plan(self.plan)
        assert session1 in plan1_sessions
        assert session2 not in plan1_sessions

        # Get sessions for plan2
        plan2_sessions = IndividualVoterSession.objects.for_group_plan(plan2)
        assert session2 in plan2_sessions
        assert session1 not in plan2_sessions


@pytest.mark.django_db
class TestVote:
    """Tests for Vote model"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='testpass123',
            first_name='Test'
        )
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category'
        )
        self.plan = GroupPlan.objects.create(creator=self.user)
        from django.utils import timezone
        self.event = Event.objects.create(
            name='Test Event',
            date=timezone.now(),
            is_active=True
        )
        self.event.category.set([self.category])
        self.bucket_event = GroupPlanEvent.objects.create(
            group_plan=self.plan,
            event=self.event,
            added_by=self.user
        )
        self.invitation = VoteInvitation.objects.create(
            group_plan=self.plan,
            created_by=self.user,
            is_active=True
        )
        self.session = IndividualVoterSession.objects.create(
            invitation=self.invitation,
            voter_name='Test Voter'
        )

    def test_unique_constraint(self):
        """Test unique together constraint"""
        # Create initial vote
        Vote.objects.create(
            group_plan_event=self.bucket_event,
            voter_session=self.session,
            direction='INTERESTED'
        )

        # Try to create duplicate - should raise IntegrityError
        with pytest.raises(IntegrityError):
            Vote.objects.create(
                group_plan_event=self.bucket_event,
                voter_session=self.session,
                direction='SKIP'
            )
