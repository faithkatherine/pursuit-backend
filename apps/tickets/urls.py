from django.urls import path

from apps.tickets import views

app_name = 'tickets'

urlpatterns = [
    path(
        'verify/<str:token>/',
        views.TicketVerifyView.as_view(),
        name='verify'
    ),
    path(
        'use/<str:token>/',
        views.TicketUseView.as_view(),
        name='use'
    ),
    path(
        'order/<uuid:order_id>/',
        views.TicketListView.as_view(),
        name='list-by-order'
    ),
]
