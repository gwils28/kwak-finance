from kwak_api.main import create_app


def test_operation_ids_are_the_handler_names() -> None:
    """They become the function names of the generated TypeScript SDK."""
    schema = create_app().openapi()
    ids = {op["operationId"] for path in schema["paths"].values() for op in path.values()}
    assert {"health", "login", "totpVerify", "me", "logout"} <= ids
