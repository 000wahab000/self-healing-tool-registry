from __future__ import annotations

import copy

import httpx
import pytest

from healer.canonical import sha256
from healer.diagnose import flatten_request
from healer.openapi_loader import fetch_spec, operations, resolve_refs

SPEC = {
    "openapi": "3.1.0",
    "info": {"title": "FastAPI", "version": "0.1.0"},
    "paths": {
        "/tickets": {
            "post": {
                "summary": "Create Ticket",
                "description": "Open a ticket.",
                "operationId": "create_ticket",
                "security": [{"HTTPBearer": []}],
                "parameters": [
                    {
                        "name": "x-tenant-id",
                        "in": "header",
                        "required": True,
                        "schema": {"type": "string", "title": "X-Tenant-Id"},
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "schema": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                    },
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/TicketIn"}
                        }
                    },
                },
                "responses": {
                    "422": {
                        "description": "Validation Error",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Problem"}
                            }
                        },
                    },
                    "200": {
                        "description": "Successful Response",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/TicketOut"}
                            }
                        },
                    },
                },
            }
        },
        "/health": {"get": {"summary": "no operation id", "responses": {}}},
        "/users/{uid}": {
            "get": {
                "operationId": "get_user_by_id",
                "parameters": [
                    {
                        "name": "uid",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {"204": {"description": "No Content"}},
            }
        },
    },
    "components": {
        "schemas": {
            "TicketIn": {
                "type": "object",
                "title": "TicketIn",
                "required": ["user_id", "title", "owner"],
                "properties": {
                    "user_id": {"type": "string", "title": "User Id"},
                    "title": {"type": "string", "title": "Title"},
                    "note": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "title": "Note",
                    },
                    "owner": {
                        "$ref": "#/components/schemas/Owner",
                        "description": "who owns it",
                    },
                },
            },
            "Owner": {
                "type": "object",
                "title": "Owner",
                "required": ["id"],
                "properties": {"id": {"type": "integer", "title": "Id"}},
            },
            "TicketOut": {
                "type": "object",
                "required": ["ticket_id"],
                "properties": {"ticket_id": {"type": "string"}},
            },
            "Problem": {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
        "securitySchemes": {"HTTPBearer": {"type": "http", "scheme": "bearer"}},
    },
}


def test_resolve_refs_inlines_and_merges_sibling_keywords() -> None:
    out = resolve_refs(SPEC)
    owner = out["paths"]["/tickets"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]["properties"]["owner"]
    assert owner["properties"] == {"id": {"type": "integer", "title": "Id"}}
    assert owner["description"] == "who owns it"
    assert "$ref" not in repr(out)


def test_resolve_refs_does_not_mutate_input() -> None:
    before = copy.deepcopy(SPEC)
    resolve_refs(SPEC)
    assert SPEC == before


def test_resolve_refs_survives_recursive_schemas() -> None:
    spec = {
        "components": {
            "schemas": {
                "Node": {
                    "type": "object",
                    "properties": {
                        "child": {"$ref": "#/components/schemas/Node"},
                        "v": {"type": "string"},
                    },
                }
            }
        },
        "x": {"$ref": "#/components/schemas/Node"},
    }
    node = resolve_refs(spec)["x"]
    assert node["properties"]["child"] == {}
    assert node["properties"]["v"] == {"type": "string"}


def test_resolve_refs_dangling_ref_is_value_error() -> None:
    with pytest.raises(ValueError):
        resolve_refs({"x": {"$ref": "#/components/schemas/Missing"}})


def test_operations_returns_the_contract_shape() -> None:
    ops = operations(resolve_refs(SPEC))
    assert sorted(ops) == ["create_ticket", "get_user_by_id"]
    op = ops["create_ticket"]
    assert set(op) == {
        "operation_id",
        "method",
        "path",
        "body_schema",
        "params",
        "security",
        "response_schema",
        "description",
    }
    assert (op["operation_id"], op["method"], op["path"]) == (
        "create_ticket",
        "POST",
        "/tickets",
    )
    assert op["description"] == "Open a ticket."
    assert op["security"] == ["bearer"]
    assert op["params"] == [
        {
            "name": "x-tenant-id",
            "in": "header",
            "required": True,
            "schema": {"type": "string", "title": "X-Tenant-Id"},
            "description": "",
        },
        {
            "name": "limit",
            "in": "query",
            "required": False,
            "schema": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            "description": "",
        },
    ]
    assert op["body_schema"]["required"] == ["user_id", "title", "owner"]
    assert op["body_schema"]["properties"]["owner"]["properties"]["id"]["type"] == (
        "integer"
    )
    assert op["response_schema"] == SPEC["components"]["schemas"]["TicketOut"]


def test_operations_without_body_security_or_json_response() -> None:
    op = operations(resolve_refs(SPEC))["get_user_by_id"]
    assert op["body_schema"] is None
    assert op["response_schema"] is None
    assert op["security"] == []
    assert op["description"] == ""
    assert op["method"] == "GET"


def test_operations_picks_the_lowest_2xx_json_response() -> None:
    def ok(tag: str) -> dict:
        schema = {"type": "object", "title": tag}
        return {"content": {"application/json": {"schema": schema}}}

    spec = {
        "paths": {
            "/x": {
                "post": {
                    "operationId": "x",
                    "responses": {
                        "default": ok("default"),
                        "201": ok("created"),
                        "200": {"description": "no json body"},
                        "202": ok("accepted"),
                    },
                }
            }
        }
    }
    assert operations(spec)["x"]["response_schema"]["title"] == "created"


def test_flatten_request_of_loaded_operation() -> None:
    op = operations(resolve_refs(SPEC))["create_ticket"]
    got = {k: (v["type"], v["required"]) for k, v in flatten_request(op).items()}
    assert got == {
        ("body", "user_id"): ("str", True),
        ("body", "title"): ("str", True),
        ("body", "note"): ("str", False),
        ("body", "owner", "id"): ("int", True),
        ("header", "x-tenant-id"): ("str", True),
        ("query", "limit"): ("int", False),
        ("header", "authorization"): ("str", True),
    }
    assert flatten_request(op)[("body", "owner", "id")]["description"] == ""


async def test_fetch_spec_returns_resolved_spec_and_raw_hash() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/openapi.json"
        return httpx.Response(200, json=SPEC)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://mock"
    ) as client:
        spec, digest = await fetch_spec(client)
    assert digest == sha256(SPEC)
    assert "$ref" not in repr(spec)
    assert "create_ticket" in operations(spec)


async def test_fetch_spec_error_status_raises() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(500)),
        base_url="http://mock",
    ) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await fetch_spec(client)
