import json


class GraphQLClient:
    """
    Thin wrapper around Django test client for executing GraphQL operations.

    Handles authentication headers automatically when a user is provided.
    Use `execute()` for both queries and mutations.

    Usage:
        # Authenticated
        gql = GraphQLClient(client, user=some_user)
        response = gql.execute(MY_MUTATION, variables={"key": "value"})

        # Anonymous
        gql = GraphQLClient(client)
        response = gql.execute(MY_QUERY)
    """

    GRAPHQL_URL = "/graphql/"

    def __init__(self, client, user=None):
        self.client = client
        self.user = user
        self._headers = {}

        if user is not None:
            from apps.users.authentication import JWTService

            token = JWTService.generate_access_token(user)
            self._headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"

    def execute(self, query: str, variables: dict = None) -> dict:
        """Execute a GraphQL query or mutation. Returns parsed JSON response."""
        body = json.dumps({"query": query, "variables": variables or {}})
        response = self.client.post(
            self.GRAPHQL_URL,
            body,
            content_type="application/json",
            **self._headers,
        )
        return response.json()
