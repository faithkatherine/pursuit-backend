"""
Seed group plan data for testing.
Creates a CLOSED plan with votes and a DRAFT plan for faithcathy12@gmail.com

Usage: python manage.py seed_group_plans
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from apps.users.models import User
from apps.events.models import Event
from apps.group_plans.models import (
    GroupPlan,
    GroupPlanEvent,
    VoteInvitation,
    IndividualVoterSession,
    Vote,
)


class Command(BaseCommand):
    help = "Seed group plans data for testing"

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING("\n🎲 Seeding group plans data...\n")
        )

        with transaction.atomic():
            # Get or verify user
            try:
                user = User.objects.get(email="faithcathy12@gmail.com")
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Found user: {user.email} ({user.first_name})\n"
                    )
                )
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        "✗ User faithcathy12@gmail.com not found. Please create user first.\n"
                    )
                )
                return

            # Get some events for the buckets
            events = list(Event.objects.filter(is_active=True).order_by('?')[:15])
            if len(events) < 10:
                self.stdout.write(
                    self.style.ERROR(
                        "✗ Not enough events found. Please seed events first.\n"
                    )
                )
                return

            # Clear existing group plans for this user
            GroupPlan.objects.filter(creator=user).delete()
            self.stdout.write("🗑️  Cleared existing group plans\n")

            # Create CLOSED plan with votes
            closed_plan = self._create_closed_plan(user, events[:5])
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Created CLOSED plan: {closed_plan.display_name}\n"
                )
            )

            # Create OPEN (active) plan with partial votes
            open_plan = self._create_open_plan(user, events[5:10])
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Created OPEN plan: {open_plan.display_name}\n"
                )
            )

            # Create DRAFT plan
            draft_plan = self._create_draft_plan(user, events[10:])
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Created DRAFT plan: {draft_plan.display_name}\n"
                )
            )

            self.stdout.write(
                self.style.SUCCESS(
                    "\n✨ Successfully seeded group plans data!\n"
                )
            )

    def _create_closed_plan(self, user, events):
        """Create a CLOSED group plan with completed votes"""
        # Create group plan
        plan = GroupPlan.objects.create(
            creator=user,
            name="",  # Will use auto-generated name
            status='CLOSED',
            created_at=timezone.now() - timedelta(days=7),
        )

        # Add events to the plan
        bucket_events = []
        for i, event in enumerate(events):
            be = GroupPlanEvent.objects.create(
                group_plan=plan,
                event=event,
                added_by=user,
                ordering=i,
            )
            bucket_events.append(be)

        # Create invitation
        invitation = VoteInvitation.objects.create(
            group_plan=plan,
            created_by=user,
            is_active=False,  # Closed
        )

        # Create voter sessions (creator + 3 friends)
        voter_names = [
            (user.first_name, user),  # Creator (registered)
            ("Alex", None),  # Anonymous friend 1
            ("Jordan", None),  # Anonymous friend 2
            ("Sam", None),  # Anonymous friend 3
        ]

        sessions = []
        for name, reg_user in voter_names:
            session = IndividualVoterSession.objects.create(
                invitation=invitation,
                voter_name=name,
                registered_user=reg_user,
            )
            sessions.append(session)

        # Create votes - different patterns for variety
        # Event 0: Everyone interested (4/4)
        for session in sessions:
            Vote.objects.create(
                group_plan_event=bucket_events[0],
                voter_session=session,
                direction='INTERESTED',
            )

        # Event 1: 3/4 interested
        for session in sessions[:3]:
            Vote.objects.create(
                group_plan_event=bucket_events[1],
                voter_session=session,
                direction='INTERESTED',
            )
        Vote.objects.create(
            group_plan_event=bucket_events[1],
            voter_session=sessions[3],
            direction='SKIP',
        )

        # Event 2: 2/4 interested
        for session in sessions[:2]:
            Vote.objects.create(
                group_plan_event=bucket_events[2],
                voter_session=session,
                direction='INTERESTED',
            )
        for session in sessions[2:]:
            Vote.objects.create(
                group_plan_event=bucket_events[2],
                voter_session=session,
                direction='SKIP',
            )

        # Event 3: 1/4 interested (mostly skipped)
        Vote.objects.create(
            group_plan_event=bucket_events[3],
            voter_session=sessions[0],
            direction='INTERESTED',
        )
        for session in sessions[1:]:
            Vote.objects.create(
                group_plan_event=bucket_events[3],
                voter_session=session,
                direction='SKIP',
            )

        # Event 4: 3/4 interested
        for session in sessions[1:]:
            Vote.objects.create(
                group_plan_event=bucket_events[4],
                voter_session=session,
                direction='INTERESTED',
            )
        Vote.objects.create(
            group_plan_event=bucket_events[4],
            voter_session=sessions[0],
            direction='SKIP',
        )

        return plan

    def _create_open_plan(self, user, events):
        """Create an OPEN group plan with partial voting"""
        # Create group plan
        plan = GroupPlan.objects.create(
            creator=user,
            name="This Weekend's Picks",
            status='OPEN',
            created_at=timezone.now() - timedelta(days=2),
        )

        # Add events to the plan
        bucket_events = []
        for i, event in enumerate(events):
            be = GroupPlanEvent.objects.create(
                group_plan=plan,
                event=event,
                added_by=user,
                ordering=i,
            )
            bucket_events.append(be)

        # Create invitation
        invitation = VoteInvitation.objects.create(
            group_plan=plan,
            created_by=user,
            is_active=True,  # Active voting
        )

        # Create voter sessions (creator + 2 friends who have voted, 1 pending)
        voter_names = [
            (user.first_name, user),  # Creator (voted)
            ("Chris", None),  # Friend 1 (voted)
            ("Taylor", None),  # Friend 2 (voted)
            ("Morgan", None),  # Friend 3 (pending - session exists but no votes)
        ]

        sessions = []
        for name, reg_user in voter_names:
            session = IndividualVoterSession.objects.create(
                invitation=invitation,
                voter_name=name,
                registered_user=reg_user,
            )
            sessions.append(session)

        # Create votes - only first 3 voters have voted (1 pending)
        # Event 0: 3/3 voted interested
        for session in sessions[:3]:
            Vote.objects.create(
                group_plan_event=bucket_events[0],
                voter_session=session,
                direction='INTERESTED',
            )

        # Event 1: 2/3 voted
        for session in sessions[:2]:
            Vote.objects.create(
                group_plan_event=bucket_events[1],
                voter_session=session,
                direction='INTERESTED',
            )

        # Event 2: 3/3 voted, mixed
        Vote.objects.create(
            group_plan_event=bucket_events[2],
            voter_session=sessions[0],
            direction='INTERESTED',
        )
        Vote.objects.create(
            group_plan_event=bucket_events[2],
            voter_session=sessions[1],
            direction='SKIP',
        )
        Vote.objects.create(
            group_plan_event=bucket_events[2],
            voter_session=sessions[2],
            direction='INTERESTED',
        )

        # Events 3 and 4: Only 1-2 votes so far
        Vote.objects.create(
            group_plan_event=bucket_events[3],
            voter_session=sessions[0],
            direction='INTERESTED',
        )

        Vote.objects.create(
            group_plan_event=bucket_events[4],
            voter_session=sessions[1],
            direction='SKIP',
        )

        return plan

    def _create_draft_plan(self, user, events):
        """Create a DRAFT group plan"""
        # Create group plan
        plan = GroupPlan.objects.create(
            creator=user,
            name="Weekend Vibes",
            status='DRAFT',
            created_at=timezone.now() - timedelta(hours=2),
        )

        # Add events to the plan
        for i, event in enumerate(events[:5]):
            GroupPlanEvent.objects.create(
                group_plan=plan,
                event=event,
                added_by=user,
                ordering=i,
            )

        # Create invitation but no votes yet (draft stage)
        VoteInvitation.objects.create(
            group_plan=plan,
            created_by=user,
            is_active=True,  # Active but not shared yet
        )

        return plan
