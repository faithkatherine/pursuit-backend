import pytest
from graphql_jwt.testcases import JSONWebTokenTestCase
from django.contrib.auth import get_user_model
from apps.events.models import Event
from apps.core.models import Category
from apps.group_plans.models import GroupPlan, VoteInvitation, IndividualVoterSession, GroupPlanEvent
from django.test import RequestFactory
from graphene.test import Client
from pursuit_backend.schema import schema

User = get_user_model()


@pytest.mark.django_db
class TestGroupPlansMutations:
    """Tests for Group Plans mutations"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test data"""
        from django.utils import timezone
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='testpass123',
            first_name='Test'
        )
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='testuser2@example.com',
            password='testpass123',
            first_name='Test2'
        )
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category'
        )
        self.event = Event.objects.create(
            name='Test Event',
            date=timezone.now(),
            is_active=True
        )
        self.event.category.set([self.category])

    def _create_context(self, user=None):
        """Helper to create GraphQL context"""
        request = self.factory.get('/')
        request.user = user or self.user
        return request

    def test_create_group_plan(self):
        """Test createGroupPlan mutation creates plan and auto-invitation"""
        client = Client(schema)
        context = self._create_context(self.user)

        mutation = '''
            mutation CreateGroupPlan($name: String) {
                createGroupPlan(name: $name) {
                    groupPlan {
                        id
                        name
                        status
                        creator {
                            id
                        }
                        invitations {
                            id
                            isActive
                        }
                    }
                }
            }
        '''

        result = client.execute(
            mutation,
            variables={'name': 'My Group Plan'},
            context=context
        )

        assert 'errors' not in result
        assert result['data']['createGroupPlan']['groupPlan']['name'] == 'My Group Plan'
        assert result['data']['createGroupPlan']['groupPlan']['status'] == 'DRAFT'
        assert len(result['data']['createGroupPlan']['groupPlan']['invitations']) == 1
        assert result['data']['createGroupPlan']['groupPlan']['invitations'][0]['isActive'] is True

    def test_create_group_plan_requires_auth(self):
        """Test createGroupPlan requires authentication"""
        from django.contrib.auth.models import AnonymousUser
        client = Client(schema)
        context = self._create_context(user=None)
        context.user = AnonymousUser()

        mutation = '''
            mutation CreateGroupPlan {
                createGroupPlan {
                    groupPlan {
                        id
                    }
                }
            }
        '''

        result = client.execute(mutation, context=context)
        assert 'errors' in result
        assert 'Authentication required' in str(result['errors'])

    def test_add_event_to_bucket(self):
        """Test addEventToBucket mutation"""
        client = Client(schema)
        context = self._create_context(self.user)

        plan = GroupPlan.objects.create(creator=self.user, status='DRAFT')

        mutation = '''
            mutation AddEventToBucket($groupPlanId: ID!, $eventId: ID!) {
                addEventToBucket(groupPlanId: $groupPlanId, eventId: $eventId) {
                    groupPlanEvent {
                        id
                        event {
                            id
                        }
                        ordering
                    }
                }
            }
        '''

        result = client.execute(
            mutation,
            variables={'groupPlanId': str(plan.id), 'eventId': str(self.event.id)},
            context=context
        )

        assert 'errors' not in result
        assert result['data']['addEventToBucket']['groupPlanEvent']['ordering'] == 1
        assert GroupPlanEvent.objects.filter(group_plan=plan, event=self.event).exists()

    def test_add_event_duplicate_rejected(self):
        """Test adding same event twice is rejected"""
        client = Client(schema)
        context = self._create_context(self.user)

        plan = GroupPlan.objects.create(creator=self.user, status='DRAFT')
        GroupPlanEvent.objects.create(group_plan=plan, event=self.event, added_by=self.user)

        mutation = '''
            mutation AddEventToBucket($groupPlanId: ID!, $eventId: ID!) {
                addEventToBucket(groupPlanId: $groupPlanId, eventId: $eventId) {
                    groupPlanEvent {
                        id
                    }
                }
            }
        '''

        result = client.execute(
            mutation,
            variables={'groupPlanId': str(plan.id), 'eventId': str(self.event.id)},
            context=context
        )

        assert 'errors' in result
        assert 'Event already in bucket' in str(result['errors'])

    def test_add_event_non_creator_rejected(self):
        """Test non-creator cannot add events"""
        client = Client(schema)
        context = self._create_context(self.user2)

        plan = GroupPlan.objects.create(creator=self.user, status='DRAFT')

        mutation = '''
            mutation AddEventToBucket($groupPlanId: ID!, $eventId: ID!) {
                addEventToBucket(groupPlanId: $groupPlanId, eventId: $eventId) {
                    groupPlanEvent {
                        id
                    }
                }
            }
        '''

        result = client.execute(
            mutation,
            variables={'groupPlanId': str(plan.id), 'eventId': str(self.event.id)},
            context=context
        )

        assert 'errors' in result
        assert 'Only the creator can add events' in str(result['errors'])

    def test_remove_event_from_bucket(self):
        """Test removeEventFromBucket mutation"""
        client = Client(schema)
        context = self._create_context(self.user)

        plan = GroupPlan.objects.create(creator=self.user, status='DRAFT')
        bucket_event = GroupPlanEvent.objects.create(
            group_plan=plan,
            event=self.event,
            added_by=self.user
        )

        mutation = '''
            mutation RemoveEventFromBucket($groupPlanEventId: ID!) {
                removeEventFromBucket(groupPlanEventId: $groupPlanEventId) {
                    success
                }
            }
        '''

        result = client.execute(
            mutation,
            variables={'groupPlanEventId': str(bucket_event.id)},
            context=context
        )

        assert 'errors' not in result
        assert result['data']['removeEventFromBucket']['success'] is True
        assert not GroupPlanEvent.objects.filter(id=bucket_event.id).exists()

    def test_cast_vote_creates_vote(self):
        """Test castVote mutation creates vote"""
        client = Client(schema)

        plan = GroupPlan.objects.create(creator=self.user, status='OPEN')
        invitation = VoteInvitation.objects.create(
            group_plan=plan,
            created_by=self.user,
            is_active=True
        )
        session = IndividualVoterSession.objects.create(
            invitation=invitation,
            voter_name='Test Voter'
        )
        bucket_event = GroupPlanEvent.objects.create(
            group_plan=plan,
            event=self.event,
            added_by=self.user
        )

        mutation = '''
            mutation CastVote($groupPlanEventId: ID!, $sessionToken: String!, $direction: VoteDirectionEnum!) {
                castVote(groupPlanEventId: $groupPlanEventId, sessionToken: $sessionToken, direction: $direction) {
                    vote {
                        id
                        direction
                    }
                }
            }
        '''

        context = self._create_context()
        result = client.execute(
            mutation,
            variables={
                'groupPlanEventId': str(bucket_event.id),
                'sessionToken': str(session.session_token),
                'direction': 'INTERESTED'
            },
            context=context
        )

        assert 'errors' not in result
        assert result['data']['castVote']['vote']['direction'] == 'INTERESTED'

    def test_cast_vote_upserts(self):
        """Test castVote updates existing vote"""
        from apps.group_plans.models import Vote

        client = Client(schema)

        plan = GroupPlan.objects.create(creator=self.user, status='OPEN')
        invitation = VoteInvitation.objects.create(
            group_plan=plan,
            created_by=self.user,
            is_active=True
        )
        session = IndividualVoterSession.objects.create(
            invitation=invitation,
            voter_name='Test Voter'
        )
        bucket_event = GroupPlanEvent.objects.create(
            group_plan=plan,
            event=self.event,
            added_by=self.user
        )

        # Create initial vote
        Vote.objects.create(
            group_plan_event=bucket_event,
            voter_session=session,
            direction='SKIP'
        )

        mutation = '''
            mutation CastVote($groupPlanEventId: ID!, $sessionToken: String!, $direction: VoteDirectionEnum!) {
                castVote(groupPlanEventId: $groupPlanEventId, sessionToken: $sessionToken, direction: $direction) {
                    vote {
                        id
                        direction
                    }
                }
            }
        '''

        context = self._create_context()
        result = client.execute(
            mutation,
            variables={
                'groupPlanEventId': str(bucket_event.id),
                'sessionToken': str(session.session_token),
                'direction': 'INTERESTED'
            },
            context=context
        )

        assert 'errors' not in result
        assert result['data']['castVote']['vote']['direction'] == 'INTERESTED'
        # Verify only one vote exists
        assert Vote.objects.filter(
            group_plan_event=bucket_event,
            voter_session=session
        ).count() == 1

    def test_cast_vote_invalid_session_rejected(self):
        """Test castVote with invalid session token fails"""
        import uuid
        client = Client(schema)

        plan = GroupPlan.objects.create(creator=self.user, status='OPEN')
        bucket_event = GroupPlanEvent.objects.create(
            group_plan=plan,
            event=self.event,
            added_by=self.user
        )

        mutation = '''
            mutation CastVote($groupPlanEventId: ID!, $sessionToken: String!, $direction: VoteDirectionEnum!) {
                castVote(groupPlanEventId: $groupPlanEventId, sessionToken: $sessionToken, direction: $direction) {
                    vote {
                        id
                    }
                }
            }
        '''

        context = self._create_context()
        # Use a valid UUID format that doesn't exist in the database
        fake_uuid = str(uuid.uuid4())
        result = client.execute(
            mutation,
            variables={
                'groupPlanEventId': str(bucket_event.id),
                'sessionToken': fake_uuid,
                'direction': 'INTERESTED'
            },
            context=context
        )

        assert 'errors' in result
        assert 'Invalid session token' in str(result['errors'])

    def test_create_voter_session_anonymous(self):
        """Test createVoterSession for anonymous user"""
        client = Client(schema)

        plan = GroupPlan.objects.create(creator=self.user, status='OPEN')
        invitation = VoteInvitation.objects.create(
            group_plan=plan,
            created_by=self.user,
            is_active=True
        )

        mutation = '''
            mutation CreateVoterSession($shareToken: String!, $voterName: String) {
                createVoterSession(shareToken: $shareToken, voterName: $voterName) {
                    voterSession {
                        id
                        voterName
                        displayInitial
                        displayColor
                    }
                }
            }
        '''

        context = self._create_context()
        from django.contrib.auth.models import AnonymousUser
        context.user = AnonymousUser()
        result = client.execute(
            mutation,
            variables={
                'shareToken': str(invitation.share_token),
                'voterName': 'Anonymous Voter'
            },
            context=context
        )

        assert 'errors' not in result
        assert result['data']['createVoterSession']['voterSession']['voterName'] == 'Anonymous Voter'
        assert result['data']['createVoterSession']['voterSession']['displayInitial'] == 'A'

    def test_create_voter_session_authenticated(self):
        """Test createVoterSession auto-populates registered_user"""
        client = Client(schema)

        plan = GroupPlan.objects.create(creator=self.user, status='OPEN')
        invitation = VoteInvitation.objects.create(
            group_plan=plan,
            created_by=self.user,
            is_active=True
        )

        mutation = '''
            mutation CreateVoterSession($shareToken: String!, $voterName: String) {
                createVoterSession(shareToken: $shareToken, voterName: $voterName) {
                    voterSession {
                        id
                        voterName
                    }
                }
            }
        '''

        context = self._create_context(self.user2)
        result = client.execute(
            mutation,
            variables={
                'shareToken': str(invitation.share_token),
                'voterName': 'Test Voter'
            },
            context=context
        )

        assert 'errors' not in result
        session = IndividualVoterSession.objects.get(
            id=result['data']['createVoterSession']['voterSession']['id']
        )
        assert session.registered_user == self.user2

    def test_open_group_plan_for_voting(self):
        """Test openGroupPlanForVoting sets status to OPEN"""
        client = Client(schema)
        context = self._create_context(self.user)

        plan = GroupPlan.objects.create(creator=self.user, status='DRAFT')

        mutation = '''
            mutation OpenGroupPlanForVoting($groupPlanId: ID!) {
                openGroupPlanForVoting(groupPlanId: $groupPlanId) {
                    groupPlan {
                        id
                        status
                    }
                }
            }
        '''

        result = client.execute(
            mutation,
            variables={'groupPlanId': str(plan.id)},
            context=context
        )

        assert 'errors' not in result
        assert result['data']['openGroupPlanForVoting']['groupPlan']['status'] == 'OPEN'
        plan.refresh_from_db()
        assert plan.status == 'OPEN'

    def test_close_group_plan(self):
        """Test closeGroupPlan sets status to CLOSED"""
        client = Client(schema)
        context = self._create_context(self.user)

        plan = GroupPlan.objects.create(creator=self.user, status='OPEN')

        mutation = '''
            mutation CloseGroupPlan($groupPlanId: ID!) {
                closeGroupPlan(groupPlanId: $groupPlanId) {
                    groupPlan {
                        id
                        status
                    }
                }
            }
        '''

        result = client.execute(
            mutation,
            variables={'groupPlanId': str(plan.id)},
            context=context
        )

        assert 'errors' not in result
        assert result['data']['closeGroupPlan']['groupPlan']['status'] == 'CLOSED'
        plan.refresh_from_db()
        assert plan.status == 'CLOSED'


@pytest.mark.django_db
class TestGroupPlansQueries:
    """Tests for Group Plans queries"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test data"""
        self.factory = RequestFactory()
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

    def _create_context(self, user=None):
        """Helper to create GraphQL context"""
        request = self.factory.get('/')
        request.user = user or self.user
        return request

    def test_group_plan_by_share_token(self):
        """Test groupPlanByShareToken query"""
        client = Client(schema)

        plan = GroupPlan.objects.create(creator=self.user, name='Test Plan', status='OPEN')
        invitation = VoteInvitation.objects.create(
            group_plan=plan,
            created_by=self.user,
            is_active=True
        )

        query = '''
            query GroupPlanByShareToken($shareToken: String!) {
                groupPlanByShareToken(shareToken: $shareToken) {
                    id
                    name
                    status
                }
            }
        '''

        context = self._create_context()
        result = client.execute(
            query,
            variables={'shareToken': str(invitation.share_token)},
            context=context
        )

        assert 'errors' not in result
        assert result['data']['groupPlanByShareToken']['name'] == 'Test Plan'

    def test_group_plan_by_share_token_inactive_fails(self):
        """Test inactive invitation returns error"""
        client = Client(schema)

        plan = GroupPlan.objects.create(creator=self.user, status='OPEN')
        invitation = VoteInvitation.objects.create(
            group_plan=plan,
            created_by=self.user,
            is_active=False
        )

        query = '''
            query GroupPlanByShareToken($shareToken: String!) {
                groupPlanByShareToken(shareToken: $shareToken) {
                    id
                }
            }
        '''

        context = self._create_context()
        result = client.execute(
            query,
            variables={'shareToken': str(invitation.share_token)},
            context=context
        )

        assert 'errors' in result
        assert 'Invalid or inactive invitation' in str(result['errors'])

    def test_my_group_plans(self):
        """Test myGroupPlans returns user's plans"""
        client = Client(schema)

        plan1 = GroupPlan.objects.create(creator=self.user, name='Plan 1')
        plan2 = GroupPlan.objects.create(creator=self.user, name='Plan 2')

        query = '''
            query MyGroupPlans {
                myGroupPlans {
                    id
                    name
                }
            }
        '''

        context = self._create_context(self.user)
        result = client.execute(query, context=context)

        assert 'errors' not in result
        assert len(result['data']['myGroupPlans']) == 2
        names = [p['name'] for p in result['data']['myGroupPlans']]
        assert 'Plan 1' in names
        assert 'Plan 2' in names

    def test_my_group_plans_requires_auth(self):
        """Test myGroupPlans requires authentication"""
        client = Client(schema)

        query = '''
            query MyGroupPlans {
                myGroupPlans {
                    id
                }
            }
        '''

        context = self._create_context()
        from django.contrib.auth.models import AnonymousUser
        context.user = AnonymousUser()
        result = client.execute(query, context=context)

        assert 'errors' in result
        assert 'Authentication required' in str(result['errors'])

    def test_event_suggestions_excludes_added_events(self):
        """Test eventSuggestionsForGroupPlan excludes already-added events"""
        from django.utils import timezone
        client = Client(schema)

        event1 = Event.objects.create(
            name='Event 1',
            date=timezone.now(),
            is_active=True,
            going_count=10
        )
        event1.category.set([self.category])
        event2 = Event.objects.create(
            name='Event 2',
            date=timezone.now(),
            is_active=True,
            going_count=20
        )
        event2.category.set([self.category])

        plan = GroupPlan.objects.create(creator=self.user, status='DRAFT')
        # Add event1 to plan
        GroupPlanEvent.objects.create(
            group_plan=plan,
            event=event1,
            added_by=self.user
        )

        query = '''
            query EventSuggestionsForGroupPlan($groupPlanId: ID!) {
                eventSuggestionsForGroupPlan(groupPlanId: $groupPlanId) {
                    id
                    name
                }
            }
        '''

        context = self._create_context(self.user)
        result = client.execute(
            query,
            variables={'groupPlanId': str(plan.id)},
            context=context
        )

        assert 'errors' not in result
        names = [e['name'] for e in result['data']['eventSuggestionsForGroupPlan']]
        assert 'Event 1' not in names  # Already added, should be excluded
        assert 'Event 2' in names

    def test_event_suggestions_returns_max_7(self):
        """Test eventSuggestionsForGroupPlan returns max 7 events"""
        from django.utils import timezone
        client = Client(schema)

        # Create 10 events
        for i in range(10):
            event = Event.objects.create(
                name=f'Event {i}',
                date=timezone.now(),
                is_active=True,
                going_count=i
            )
            event.category.set([self.category])

        plan = GroupPlan.objects.create(creator=self.user, status='DRAFT')

        query = '''
            query EventSuggestionsForGroupPlan($groupPlanId: ID!) {
                eventSuggestionsForGroupPlan(groupPlanId: $groupPlanId) {
                    id
                }
            }
        '''

        context = self._create_context(self.user)
        result = client.execute(
            query,
            variables={'groupPlanId': str(plan.id)},
            context=context
        )

        assert 'errors' not in result
        assert len(result['data']['eventSuggestionsForGroupPlan']) <= 7


@pytest.mark.django_db
class TestPermissions:
    """Tests for permission checks"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test data"""
        self.factory = RequestFactory()
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123',
            first_name='User1'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123',
            first_name='User2'
        )

    def _create_context(self, user):
        """Helper to create GraphQL context"""
        request = self.factory.get('/')
        request.user = user
        return request

    def test_non_creator_cannot_open_plan(self):
        """Test only creator can open plan for voting"""
        client = Client(schema)

        plan = GroupPlan.objects.create(creator=self.user1, status='DRAFT')

        mutation = '''
            mutation OpenGroupPlanForVoting($groupPlanId: ID!) {
                openGroupPlanForVoting(groupPlanId: $groupPlanId) {
                    groupPlan {
                        id
                    }
                }
            }
        '''

        context = self._create_context(self.user2)
        result = client.execute(
            mutation,
            variables={'groupPlanId': str(plan.id)},
            context=context
        )

        assert 'errors' in result
        assert 'Only the creator can open the plan' in str(result['errors'])

    def test_non_creator_cannot_close_plan(self):
        """Test only creator can close plan"""
        client = Client(schema)

        plan = GroupPlan.objects.create(creator=self.user1, status='OPEN')

        mutation = '''
            mutation CloseGroupPlan($groupPlanId: ID!) {
                closeGroupPlan(groupPlanId: $groupPlanId) {
                    groupPlan {
                        id
                    }
                }
            }
        '''

        context = self._create_context(self.user2)
        result = client.execute(
            mutation,
            variables={'groupPlanId': str(plan.id)},
            context=context
        )

        assert 'errors' in result
        assert 'Only the creator can close the plan' in str(result['errors'])

    def test_non_creator_cannot_rename_plan(self):
        """Test only creator can rename plan"""
        client = Client(schema)

        plan = GroupPlan.objects.create(creator=self.user1, name='Original Name', status='DRAFT')

        mutation = '''
            mutation UpdateGroupPlanName($groupPlanId: ID!, $name: String!) {
                updateGroupPlanName(groupPlanId: $groupPlanId, name: $name) {
                    groupPlan {
                        id
                    }
                }
            }
        '''

        context = self._create_context(self.user2)
        result = client.execute(
            mutation,
            variables={'groupPlanId': str(plan.id), 'name': 'New Name'},
            context=context
        )

        assert 'errors' in result
        assert 'Only the creator can rename the plan' in str(result['errors'])
