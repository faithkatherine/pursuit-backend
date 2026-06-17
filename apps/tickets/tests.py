import string
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.events.models import Event, TicketTier
from apps.organizers.models import OrganizerProfile
from apps.payments.models import Order, OrderItem
from apps.tickets.models import Ticket, create_ticket_with_retry, generate_ticket_token

User = get_user_model()


@pytest.mark.django_db
class TestTicketCreation:
    """Tickets are created when payment succeeds."""

    def test_one_ticket_per_physical_ticket(self):
        """
        OrderItem quantity=2 → 2 Ticket records.
        OrderItem quantity=1 → 1 Ticket record.
        """
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        organizer = OrganizerProfile.objects.create(
            user=user,
            business_name='Test Organizer'
        )
        event = Event.objects.create(
            name='Test Event',
            organizer=organizer,
            date=timezone.now() + timedelta(days=7)
        )
        tier = TicketTier.objects.create(
            event=event,
            name='General',
            price=100,
            capacity=10,
            available=10
        )
        order = Order.objects.create(
            user=user,
            event=event,
            quantity=2,
            subtotal=200,
            platform_fee=4,
            total=200,
            status='paid',
            idempotency_key='test123',
            attendee_name='John Doe',
            attendee_email='john@example.com'
        )
        order_item = OrderItem.objects.create(
            order=order,
            tier=tier,
            quantity=2,
            unit_price=100
        )

        # Create tickets
        for _ in range(order_item.quantity):
            create_ticket_with_retry(
                order_item=order_item,
                attendee_name=order.attendee_name,
                attendee_email=order.attendee_email,
            )

        assert Ticket.objects.filter(order_item=order_item).count() == 2

    def test_each_ticket_has_unique_token(self):
        """Two tickets from same order have different tokens."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        organizer = OrganizerProfile.objects.create(
            user=user,
            business_name='Test Organizer'
        )
        event = Event.objects.create(
            name='Test Event',
            organizer=organizer,
            date=timezone.now() + timedelta(days=7)
        )
        tier = TicketTier.objects.create(
            event=event,
            name='General',
            price=100,
            capacity=10,
            available=10
        )
        order = Order.objects.create(
            user=user,
            event=event,
            quantity=2,
            subtotal=200,
            platform_fee=4,
            total=200,
            status='paid',
            idempotency_key='test123',
            attendee_name='John Doe',
            attendee_email='john@example.com'
        )
        order_item = OrderItem.objects.create(
            order=order,
            tier=tier,
            quantity=2,
            unit_price=100
        )

        ticket1 = create_ticket_with_retry(
            order_item=order_item,
            attendee_name=order.attendee_name,
            attendee_email=order.attendee_email,
        )
        ticket2 = create_ticket_with_retry(
            order_item=order_item,
            attendee_name=order.attendee_name,
            attendee_email=order.attendee_email,
        )

        assert ticket1.token != ticket2.token

    def test_token_is_20_chars_uppercase_alphanumeric(self):
        """Token format: 20 chars, [A-Z0-9] only."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        organizer = OrganizerProfile.objects.create(
            user=user,
            business_name='Test Organizer'
        )
        event = Event.objects.create(
            name='Test Event',
            organizer=organizer,
            date=timezone.now() + timedelta(days=7)
        )
        tier = TicketTier.objects.create(
            event=event,
            name='General',
            price=100,
            capacity=10,
            available=10
        )
        order = Order.objects.create(
            user=user,
            event=event,
            quantity=1,
            subtotal=100,
            platform_fee=2,
            total=100,
            status='paid',
            idempotency_key='test123',
            attendee_name='John Doe',
            attendee_email='john@example.com'
        )
        order_item = OrderItem.objects.create(
            order=order,
            tier=tier,
            quantity=1,
            unit_price=100
        )

        ticket = create_ticket_with_retry(
            order_item=order_item,
            attendee_name=order.attendee_name,
            attendee_email=order.attendee_email,
        )

        assert len(ticket.token) == 20
        valid = set(string.ascii_uppercase + string.digits)
        assert all(c in valid for c in ticket.token)

    def test_attendee_name_copied_from_order(self):
        """ticket.attendee_name == order.attendee_name"""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        organizer = OrganizerProfile.objects.create(
            user=user,
            business_name='Test Organizer'
        )
        event = Event.objects.create(
            name='Test Event',
            organizer=organizer,
            date=timezone.now() + timedelta(days=7)
        )
        tier = TicketTier.objects.create(
            event=event,
            name='General',
            price=100,
            capacity=10,
            available=10
        )
        order = Order.objects.create(
            user=user,
            event=event,
            quantity=1,
            subtotal=100,
            platform_fee=2,
            total=100,
            status='paid',
            idempotency_key='test123',
            attendee_name='Jane Smith',
            attendee_email='jane@example.com'
        )
        order_item = OrderItem.objects.create(
            order=order,
            tier=tier,
            quantity=1,
            unit_price=100
        )

        ticket = create_ticket_with_retry(
            order_item=order_item,
            attendee_name=order.attendee_name,
            attendee_email=order.attendee_email,
        )

        assert ticket.attendee_name == 'Jane Smith'
        assert ticket.attendee_email == 'jane@example.com'


@pytest.mark.django_db
class TestTicketVerification:
    """GET /api/tickets/verify/{token}/ endpoint."""

    def test_valid_unused_ticket_returns_valid_true(self):
        """Valid token → valid=True, already_used=False."""
        client = APIClient()
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        client.force_authenticate(user=user)

        organizer = OrganizerProfile.objects.create(
            user=user,
            business_name='Test Organizer'
        )
        event = Event.objects.create(
            name='Test Event',
            organizer=organizer,
            date=timezone.now() + timedelta(days=7)
        )
        tier = TicketTier.objects.create(
            event=event,
            name='General',
            price=100,
            capacity=10,
            available=10
        )
        order = Order.objects.create(
            user=user,
            event=event,
            quantity=1,
            subtotal=100,
            platform_fee=2,
            total=100,
            status='paid',
            idempotency_key='test123',
            attendee_name='John Doe',
            attendee_email='john@example.com'
        )
        order_item = OrderItem.objects.create(
            order=order,
            tier=tier,
            quantity=1,
            unit_price=100
        )
        ticket = create_ticket_with_retry(
            order_item=order_item,
            attendee_name=order.attendee_name,
            attendee_email=order.attendee_email,
        )

        response = client.get(f'/api/tickets/verify/{ticket.token}/')

        assert response.status_code == 200
        data = response.json()
        assert data['valid'] is True
        assert data['already_used'] is False
        assert data['token'] == ticket.token

    def test_used_ticket_returns_already_used_true(self):
        """Used ticket → valid=True, already_used=True, used_at set."""
        client = APIClient()
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        client.force_authenticate(user=user)

        organizer = OrganizerProfile.objects.create(
            user=user,
            business_name='Test Organizer'
        )
        event = Event.objects.create(
            name='Test Event',
            organizer=organizer,
            date=timezone.now() + timedelta(days=7)
        )
        tier = TicketTier.objects.create(
            event=event,
            name='General',
            price=100,
            capacity=10,
            available=10
        )
        order = Order.objects.create(
            user=user,
            event=event,
            quantity=1,
            subtotal=100,
            platform_fee=2,
            total=100,
            status='paid',
            idempotency_key='test123',
            attendee_name='John Doe',
            attendee_email='john@example.com'
        )
        order_item = OrderItem.objects.create(
            order=order,
            tier=tier,
            quantity=1,
            unit_price=100
        )
        ticket = create_ticket_with_retry(
            order_item=order_item,
            attendee_name=order.attendee_name,
            attendee_email=order.attendee_email,
        )

        # Mark ticket as used
        ticket.used_at = timezone.now()
        ticket.used_by = organizer
        ticket.save()

        response = client.get(f'/api/tickets/verify/{ticket.token}/')

        assert response.status_code == 200
        data = response.json()
        assert data['valid'] is True
        assert data['already_used'] is True
        assert data['used_at'] is not None

    def test_invalid_token_returns_valid_false(self):
        """Unknown token → valid=False, reason=invalid_token."""
        client = APIClient()
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        client.force_authenticate(user=user)

        response = client.get('/api/tickets/verify/INVALIDTOKEN123/')

        assert response.status_code == 200
        data = response.json()
        assert data['valid'] is False
        assert data['reason'] == 'invalid_token'

    def test_unauthenticated_request_returns_401(self):
        """Endpoint requires authentication."""
        client = APIClient()

        response = client.get('/api/tickets/verify/SOMETOKEN/')

        assert response.status_code == 401


@pytest.mark.django_db
class TestTicketUse:
    """POST /api/tickets/use/{token}/ endpoint."""

    def test_organizer_can_mark_own_event_ticket_used(self):
        """Organizer of event can mark ticket as used."""
        client = APIClient()
        user = User.objects.create_user(
            email='organizer@example.com',
            password='testpass123'
        )
        organizer = OrganizerProfile.objects.create(
            user=user,
            business_name='Test Organizer'
        )
        client.force_authenticate(user=user)

        event = Event.objects.create(
            name='Test Event',
            organizer=organizer,
            date=timezone.now() + timedelta(days=7)
        )
        tier = TicketTier.objects.create(
            event=event,
            name='General',
            price=100,
            capacity=10,
            available=10
        )
        buyer = User.objects.create_user(
            email='buyer@example.com',
            password='testpass123'
        )
        order = Order.objects.create(
            user=buyer,
            event=event,
            quantity=1,
            subtotal=100,
            platform_fee=2,
            total=100,
            status='paid',
            idempotency_key='test123',
            attendee_name='John Doe',
            attendee_email='john@example.com'
        )
        order_item = OrderItem.objects.create(
            order=order,
            tier=tier,
            quantity=1,
            unit_price=100
        )
        ticket = create_ticket_with_retry(
            order_item=order_item,
            attendee_name=order.attendee_name,
            attendee_email=order.attendee_email,
        )

        response = client.post(f'/api/tickets/use/{ticket.token}/')

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['used_at'] is not None

        ticket.refresh_from_db()
        assert ticket.is_used is True
        assert ticket.used_by == organizer

    def test_marking_used_twice_is_idempotent(self):
        """Calling use twice returns 200 with original used_at."""
        client = APIClient()
        user = User.objects.create_user(
            email='organizer@example.com',
            password='testpass123'
        )
        organizer = OrganizerProfile.objects.create(
            user=user,
            business_name='Test Organizer'
        )
        client.force_authenticate(user=user)

        event = Event.objects.create(
            name='Test Event',
            organizer=organizer,
            date=timezone.now() + timedelta(days=7)
        )
        tier = TicketTier.objects.create(
            event=event,
            name='General',
            price=100,
            capacity=10,
            available=10
        )
        buyer = User.objects.create_user(
            email='buyer@example.com',
            password='testpass123'
        )
        order = Order.objects.create(
            user=buyer,
            event=event,
            quantity=1,
            subtotal=100,
            platform_fee=2,
            total=100,
            status='paid',
            idempotency_key='test123',
            attendee_name='John Doe',
            attendee_email='john@example.com'
        )
        order_item = OrderItem.objects.create(
            order=order,
            tier=tier,
            quantity=1,
            unit_price=100
        )
        ticket = create_ticket_with_retry(
            order_item=order_item,
            attendee_name=order.attendee_name,
            attendee_email=order.attendee_email,
        )

        # First call
        response1 = client.post(f'/api/tickets/use/{ticket.token}/')
        assert response1.status_code == 200
        first_used_at = response1.json()['used_at']

        # Second call
        response2 = client.post(f'/api/tickets/use/{ticket.token}/')
        assert response2.status_code == 200
        second_used_at = response2.json()['used_at']

        # Should return same timestamp
        assert first_used_at == second_used_at


class TestTokenCollisionHandling:
    """generate_ticket_token and create_ticket_with_retry."""

    def test_generate_ticket_token_is_20_chars(self):
        token = generate_ticket_token()
        assert len(token) == 20

    def test_generate_ticket_token_is_uppercase_alphanumeric(self):
        valid = set(string.ascii_uppercase + string.digits)
        token = generate_ticket_token()
        assert all(c in valid for c in token)
