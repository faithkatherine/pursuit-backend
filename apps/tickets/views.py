import logging

from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tickets.models import Ticket
from apps.tickets.serializers import (
    TicketSummarySerializer,
    TicketUseResponseSerializer,
    TicketVerificationResponseSerializer,
)

logger = logging.getLogger(__name__)


class TicketVerifyView(APIView):
    """
    Verify a ticket token at the event door.
    Called by the organizer dashboard scanner page.
    Does NOT mark the ticket as used — call TicketUseView for that.
    Safe to call multiple times for the same token.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: TicketVerificationResponseSerializer,
            404: OpenApiResponse(description='Token not found'),
        },
        tags=['tickets'],
        summary='Verify a ticket token',
        description=(
            'Verifies a QR code token scanned at the event door. '
            'Returns attendee name, tier, and whether the ticket '
            'has already been used. Does not mark as used — '
            'call POST /api/tickets/use/{token}/ for that.'
        )
    )
    def get(self, request, token: str):
        try:
            ticket = Ticket.objects.select_related(
                'order_item__tier__event',
                'order_item__order',
            ).get(token=token.upper())
        except Ticket.DoesNotExist:
            return Response(
                TicketVerificationResponseSerializer({
                    'valid': False,
                    'already_used': False,
                    'token': token,
                    'attendee_name': '',
                    'tier_name': '',
                    'event_title': '',
                    'event_date': '',
                    'used_at': None,
                    'reason': 'invalid_token',
                }).data,
                status=status.HTTP_200_OK
            )

        event = ticket.event
        data = {
            'valid': True,
            'already_used': ticket.is_used,
            'token': ticket.token,
            'attendee_name': ticket.attendee_name or 'Guest',
            'tier_name': ticket.tier.name,
            'event_title': event.name,
            'event_date': str(event.date) if hasattr(event, 'date') else '',
            'used_at': ticket.used_at,
            'reason': 'already_used' if ticket.is_used else None,
        }

        logger.info(
            f'Ticket verified: {ticket.token} '
            f'event={event.name} '
            f'used={ticket.is_used}'
        )

        return Response(
            TicketVerificationResponseSerializer(data).data,
            status=status.HTTP_200_OK
        )


class TicketUseView(APIView):
    """
    Mark a ticket as used at the event door.
    Called by the organizer dashboard after confirming entry.
    Idempotent — if already used, returns the original used_at.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: TicketUseResponseSerializer,
            404: OpenApiResponse(description='Token not found'),
            403: OpenApiResponse(
                description='Organizer does not own this event'
            ),
        },
        tags=['tickets'],
        summary='Mark a ticket as used',
        description=(
            'Marks a verified ticket as used. Only the organizer '
            'of the event can call this. Idempotent — safe to call '
            'twice, returns original used_at if already marked.'
        )
    )
    def post(self, request, token: str):
        try:
            ticket = Ticket.objects.select_related(
                'order_item__tier__event__organizer',
            ).get(token=token.upper())
        except Ticket.DoesNotExist:
            return Response(
                {'error': 'invalid_token'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Verify the calling user is the organizer of this event
        try:
            organizer = request.user.organizer_profile
        except Exception:
            return Response(
                {'error': 'organizer_access_required'},
                status=status.HTTP_403_FORBIDDEN
            )

        if ticket.event.organizer != organizer:
            return Response(
                {'error': 'you_do_not_own_this_event'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Idempotent — if already used, return existing data
        if ticket.is_used:
            return Response(
                TicketUseResponseSerializer({
                    'success': True,
                    'used_at': ticket.used_at,
                    'attendee_name': ticket.attendee_name or 'Guest',
                    'tier_name': ticket.tier.name,
                }).data,
                status=status.HTTP_200_OK
            )

        # Mark as used
        ticket.used_at = timezone.now()
        ticket.used_by = organizer
        ticket.save(update_fields=['used_at', 'used_by'])

        logger.info(
            f'Ticket used: {ticket.token} '
            f'event={ticket.event.name} '
            f'organizer={organizer.business_name}'
        )

        return Response(
            TicketUseResponseSerializer({
                'success': True,
                'used_at': ticket.used_at,
                'attendee_name': ticket.attendee_name or 'Guest',
                'tier_name': ticket.tier.name,
            }).data,
            status=status.HTTP_200_OK
        )


class TicketListView(APIView):
    """
    List all tickets for an order.
    Called by the confirmation screen to get tokens for QR codes.
    User can only see their own tickets.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: TicketSummarySerializer(many=True)},
        tags=['tickets'],
        summary='List tickets for an order'
    )
    def get(self, request, order_id: str):
        from apps.payments.models import Order

        try:
            order = Order.objects.get(
                id=order_id,
                user=request.user
            )
        except Order.DoesNotExist:
            return Response(
                {'error': 'order_not_found'},
                status=status.HTTP_404_NOT_FOUND
            )

        tickets = Ticket.objects.filter(
            order_item__order=order
        ).select_related('order_item__tier')

        return Response(
            TicketSummarySerializer(tickets, many=True).data,
            status=status.HTTP_200_OK
        )
