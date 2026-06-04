def assert_graphql_success(response: dict, operation_key: str) -> dict:
    """
    Assert a GraphQL response has no errors and returns data for the given operation.

    Returns the operation data dict for further assertions.

    Usage:
        data = assert_graphql_success(response, "signIn")
        assert data["ok"] is True
    """
    assert "errors" not in response, f"Unexpected GraphQL errors: {response.get('errors')}"
    data = response.get("data", {}).get(operation_key)
    assert data is not None, f"Expected data['{operation_key}'] to be present, got: {response.get('data')}"
    return data


def assert_graphql_error(response: dict, message: str = None) -> list:
    """
    Assert a GraphQL response contains errors, optionally matching a substring.

    Returns the errors list for further assertions.

    Usage:
        assert_graphql_error(response, "Not authenticated")
    """
    errors = response.get("errors")
    assert errors is not None, "Expected GraphQL errors but response had none"
    if message:
        messages = [e.get("message", "") for e in errors]
        assert any(message in m for m in messages), f"Expected error containing '{message}', got: {messages}"
    return errors
