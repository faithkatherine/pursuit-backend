"""
URL configuration for pursuit_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)
from graphene_django.views import GraphQLView


def api_root(request):
    """API root endpoint showing available services"""
    return JsonResponse({
        'message': 'Pursuit API',
        'version': '1.0',
        'endpoints': {
            'graphql': '/graphql/',
            'admin': '/admin/',
            'health': '/api/health/',
            'payments': '/api/payments/',
            'tickets': '/api/tickets/',
            'schema': '/api/schema/',
            'docs': '/api/docs/',
        },
        'documentation': {
            'openapi': '/api/docs/ - Interactive Swagger UI documentation',
            'payments': 'See PAYMENT_SYSTEM.md for payment API documentation',
            'browsable_api': 'Payment endpoints support DRF browsable API (login via /admin/ first)',
        }
    })


urlpatterns = [
    path("", api_root, name="api-root"),
    path("admin/", admin.site.urls),
    path("graphql/", csrf_exempt(GraphQLView.as_view(graphiql=True))),
    path("api/health/", include("apps.core.urls")),
    path("api/payments/", include("apps.payments.urls")),
    path("api/tickets/", include("apps.tickets.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui"
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
