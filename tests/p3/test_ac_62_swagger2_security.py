"""AC-62 (FR-22.1): convert maps securityDefinitions to components/securitySchemes."""

from __future__ import annotations

from healer.openapi_loader import operations, resolve_refs
from healer.swagger2 import convert

DOC = {
    "swagger": "2.0",
    "info": {"title": "Sec", "version": "1"},
    "basePath": "/",
    "securityDefinitions": {
        "basicAuth": {"type": "basic"},
        "apiKeyAuth": {"type": "apiKey", "name": "X-Key", "in": "header"},
        "oauth": {
            "type": "oauth2",
            "flow": "implicit",
            "authorizationUrl": "https://example.test/auth",
            "scopes": {"read": "read things"},
        },
    },
    "paths": {
        "/oauth": {
            "get": {
                "operationId": "op_oauth",
                "security": [{"oauth": ["read"]}],
                "responses": {"200": {"description": "ok"}},
            }
        },
        "/key": {
            "get": {
                "operationId": "op_key",
                "security": [{"apiKeyAuth": []}],
                "responses": {"200": {"description": "ok"}},
            }
        },
    },
}


def test_ac_62_swagger2_security_definitions() -> None:
    converted = convert(DOC)
    schemes = converted["components"]["securitySchemes"]
    assert schemes["basicAuth"] == {"type": "http", "scheme": "basic"}
    assert schemes["apiKeyAuth"] == {"type": "apiKey", "name": "X-Key", "in": "header"}
    assert schemes["oauth"]["type"] == "oauth2"
    assert schemes["oauth"]["flows"]["implicit"]["scopes"] == {"read": "read things"}

    ops = operations(resolve_refs(converted))
    assert ops["op_oauth"]["security"] == ["bearer"]
    assert ops["op_key"]["security"] == []
