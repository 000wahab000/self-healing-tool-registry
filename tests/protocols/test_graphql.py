from __future__ import annotations

import httpx
import pytest

from healer.adapters.graphql import classify, send
from healer.graphql_loader import operations
from healer.models import ErrorClass, Side


def _introspection(user_id: str = "user_id", nested: bool = False) -> dict:
    return {
        "data": {"__schema": {"queryType": {"name": "Query"}, "mutationType": {"name": "Mutation"}, "types": [
            {"kind": "OBJECT", "name": "Query", "fields": [{"name": "get_user", "args": [{"name": user_id, "type": {"kind": "NON_NULL", "ofType": {"kind": "SCALAR", "name": "String"}}}], "type": {"kind": "OBJECT", "name": "Envelope" if nested else "User"}}]},
            {"kind": "OBJECT", "name": "Mutation", "fields": []},
            {"kind": "OBJECT", "name": "User", "fields": [{"name": "id", "type": {"kind": "SCALAR", "name": "ID"}}]},
            {"kind": "OBJECT", "name": "Envelope", "fields": [{"name": "data", "type": {"kind": "OBJECT", "name": "User"}}]},
        ]}}
    }


def test_ac_38_graphql_introspection_maps_argument_and_nested_response() -> None:
    first = operations(_introspection())["get_user"]
    changed = operations(_introspection("customer_id", True))["get_user"]
    assert first["method"] == changed["method"] == "GRAPHQL"
    assert first["path"] == changed["path"] == "/graphql"
    assert first["body_schema"]["properties"] == {"user_id": {"type": "string"}}
    assert changed["body_schema"]["properties"] == {"customer_id": {"type": "string"}}
    assert changed["response_schema"]["properties"]["data"]["properties"]["id"] == {"type": "string"}


def test_ac_38_graphql_error_paths_are_typed() -> None:
    response = httpx.Response(200, json={"errors": [{"message": "ignored", "extensions": {"code": "BAD_USER_INPUT", "argument": "user_id"}}], "data": None})
    result = classify(response)
    assert result.cls is ErrorClass.E2
    assert [(v.side, v.path) for v in result.violations] == [(Side.REQ, ["body", "user_id"])]


def test_ac_38_graphql_rejects_custom_scalars() -> None:
    raw = _introspection()
    raw["data"]["__schema"]["types"][0]["fields"][0]["args"][0]["type"]["ofType"] = {
        "kind": "SCALAR", "name": "Money"
    }
    with pytest.raises(ValueError, match="unsupported GraphQL scalar"):
        operations(raw)


@pytest.mark.asyncio
async def test_ac_38_graphql_does_not_send_nested_input_values() -> None:
    class Client:
        async def post(self, *args, **kwargs):
            pytest.fail("unsupported nested inputs must not be sent")

    result = await send(
        Client(),
        {"operation": "update", "body": {"input": {"id": "123"}}},
        1,
        spec_source=None,
    )
    assert result.cls is ErrorClass.E3
    assert result.raw_code == "UNSUPPORTED_ARGUMENT_SHAPE"


def test_ac_38_graphql_mock_admin_mutation() -> None:
    pytest.importorskip("strawberry")
    from mock_api.graphql_app import create_app

    api = create_app()
    api.set_mutation("M1")
    assert api.mutation == "M1"
    with pytest.raises(ValueError):
        api.set_mutation("unknown")
