from django.contrib.auth.models import AnonymousUser
from graphql import GraphQLError
from rest_framework.exceptions import AuthenticationFailed
from .authentication import JWTAuthentication


class JWTAuthenticationMiddleware:
    """Custom GraphQL middleware to authenticate users via JWT"""

    # Mutations that don't require authentication
    PUBLIC_MUTATIONS = {
        'signIn',
        'signUp',
        'googleSignIn',
        'refreshAccessToken',
    }

    def __init__(self):
        self.auth = JWTAuthentication()

    def resolve(self, next, root, info, **args):
        """Authenticate user before resolving GraphQL query"""
        request = info.context

        # Check if this is a public mutation that doesn't require auth
        operation_name = info.field_name
        if operation_name in self.PUBLIC_MUTATIONS:
            # Set anonymous user and allow the mutation to proceed
            if not hasattr(request, 'user'):
                request.user = AnonymousUser()
            return next(root, info, **args)

        # Skip if user is already authenticated
        if hasattr(request, 'user') and request.user.is_authenticated:
            return next(root, info, **args)

        # Try to authenticate using JWT
        try:
            auth_result = self.auth.authenticate(request)
            if auth_result:
                user, token = auth_result
                request.user = user
            else:
                # No auth header or invalid format - set anonymous user
                if not hasattr(request, 'user'):
                    request.user = AnonymousUser()
        except AuthenticationFailed as e:
            # Authentication failed - propagate as GraphQL error for token refresh
            error_message = str(e)
            print(f"[JWTAuthenticationMiddleware] Auth failed: {error_message}")

            # Determine error code based on the error message
            if 'expired' in error_message.lower():
                error_code = 'TOKEN_EXPIRED'
            else:
                error_code = 'NOT_AUTHENTICATED'

            # Set anonymous user but also raise GraphQL error
            if not hasattr(request, 'user'):
                request.user = AnonymousUser()

            raise GraphQLError(
                error_message,
                extensions={'code': error_code}
            )
        except Exception as e:
            # Other authentication errors - set anonymous user
            print(f"[JWTAuthenticationMiddleware] Unexpected auth error: {e}")
            if not hasattr(request, 'user'):
                request.user = AnonymousUser()

        return next(root, info, **args)
