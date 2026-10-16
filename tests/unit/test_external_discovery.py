from __future__ import annotations

import copy

import httpx
import pytest

from healer.connection_discovery import discover
from healer.diagnose import diff, flatten_request
from healer.models import DecisionPath, ErrorClass, Fix, LoadedSpec, Tier
from healer.openapi_loader import operations
from healer.registry import Registry
from healer.store import Store


def _loaded(raw: dict) -> LoadedSpec:
    return LoadedSpec(raw, {f"api__{key}": value for key, value in operations(raw).items()}, "hash")


def test_ac_107_filters_selection_and_reports_incompatible_operations() -> None:
    raw = {
        "paths": {
            "/users/{user_id}": {
                "parameters": [{"name": "user_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "get": {"operationId": "get_user", "responses": {}},
            },
            "/upload": {"post": {"operationId": "upload", "requestBody": {"content": {"multipart/form-data": {"schema": {}}}}, "responses": {}}},
            "/bad": {"get": {"operationId": "bad", "parameters": [{"name": "q", "in": "query", "schema": {"type": "array", "items": {"type": "string"}}}], "responses": {}}},
        }
    }
    loaded, errors = discover(_loaded(raw), {"name": "api", "selected_operations": ["get_user", "upload", "bad"]}, set())
    assert list(loaded.ops) == ["api__get_user"]
    assert {(item["operation"], item["code"]) for item in errors} == {
        ("upload", "UNSUPPORTED_MEDIA_TYPE"),
        ("bad", "UNSUPPORTED_QUERY_SERIALIZATION"),
    }
    inherited = loaded.ops["api__get_user"]["params"]
    assert inherited[0]["name"] == "user_id"
    assert ("route_params", "user_id") in flatten_request(loaded.ops["api__get_user"])


def test_ac_107_path_parameter_rename_is_a_route_param_schema_change() -> None:
    old = {"operation_id": "get", "method": "GET", "path": "/x/{old}", "body_schema": None, "params": [{"name": "old", "in": "path", "required": True, "schema": {"type": "string"}, "description": ""}], "security": [], "response_schema": None, "description": ""}
    new = {**old, "path": "/x/{new}", "params": [{**old["params"][0], "name": "new"}]}
    assert {tuple(entry["path"]) for entry in diff(old, new) if entry["change"] in {"removed", "added"}} == {
        ("route_params", "old"),
        ("route_params", "new"),
    }


async def test_ac_107_path_parameters_are_bound_encoded_and_schema_frozen() -> None:
    raw = {"paths": {"/users/{user_id}": {"get": {"operationId": "get_user", "parameters": [{"name": "user_id", "in": "path", "required": True, "schema": {"type": "string"}}], "responses": {}}}}}
    loaded = _loaded(raw)
    selected, _ = discover(loaded, {"name": "api", "selected_operations": ["get_user"]}, set())
    sent: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request.url.raw_path.decode())
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://example.test") as client:
        config = {"tools": {"api__get_user": {"postchecks": []}}}
        registry = Registry(client, config, {}, spec_source=lambda: _return(selected))
        await registry.load()
        before = registry.tools()
        assert registry.tools()[0]["parameters"]["required"] == ["user_id"]
        assert await registry.call("api__get_user", {"user_id": "a/b"}) == {"ok": True}
        assert registry.tools() == before
    assert sent == ["/users/a%2Fb"]


async def test_ac_107_configured_header_reference_materializes_for_each_attempt() -> None:
    raw = {"paths": {"/items": {"get": {"operationId": "list_items", "parameters": [{"name": "X-Account", "in": "header", "required": True, "schema": {"type": "string"}}], "responses": {}}}}}
    loaded, diagnostics = discover(_loaded(raw), {"name": "api", "selected_operations": ["list_items"]}, {"X-Account"})
    assert diagnostics == []
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["x-account"])
        return httpx.Response(200, json=[])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://example.test") as client:
        config = {"header_sources": {"X-Account": "account_ref"}, "tools": {"api__list_items": {"postchecks": []}}}
        registry = Registry(client, config, {"account_ref": "private-value"}, spec_source=lambda: _return(loaded))
        await registry.load()
        base = registry.base_doc(registry.defs["api__list_items"], {})
        assert base["header"] == {"x-account": {"ref": "config", "key": "account_ref"}}
        fix = Fix("f", {}, "api__list_items", ErrorClass.E2, [{"op": "header", "name": "X-Account", "src": {"ref": "config", "key": "account_ref"}}], [], Tier.T1, DecisionPath.diff, "h")
        assert (await registry._attempt(registry.defs["api__list_items"], base, fix)).cls is ErrorClass.OK
        assert (await registry._attempt(registry.defs["api__list_items"], base, None)).cls is ErrorClass.OK
        changed = copy.deepcopy(registry.defs["api__list_items"].base_op)
        changed["params"][0]["schema"] = {"type": "string", "enum": ["other-account"]}
        with pytest.raises(ValueError, match="HEADER_SCHEMA_INVALID"):
            registry.materialize_request(registry.defs["api__list_items"], base, fix, operation=changed)
    assert seen == ["private-value", "private-value"]


async def test_ac_107_agent_cannot_override_headers_or_inherit_client_auth() -> None:
    raw = {"paths": {"/items": {"get": {"operationId": "list_items", "responses": {}}}}}
    loaded, _ = discover(_loaded(raw), {"name": "api", "selected_operations": ["list_items"]}, set())
    sent: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append((request.headers.get("authorization", ""), request.headers.get("cookie", "")))
        return httpx.Response(200, json=[])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://example.test", headers={"Authorization": "client-secret", "Cookie": "session-secret"}) as client:
        config = {"header_sources": {}, "tools": {"api__list_items": {"postchecks": []}}}
        registry = Registry(client, config, {}, spec_source=lambda: _return(loaded))
        await registry.load()
        assert await registry.call("api__list_items", {"authorization": "agent-value"}) == {"error": "AGENT_ARG_ERROR", "tool": "api__list_items", "retry": False}
        assert await registry.call("api__list_items", {}) == []
    assert sent == [("", "")]


async def test_ac_107_secrets_are_redacted_from_tools_snapshots_and_results(tmp_path) -> None:
    raw = {"info": {"description": "private-value"}, "paths": {"/items": {"get": {"operationId": "list_items", "description": "private-value", "responses": {}}}}}
    loaded, _ = discover(_loaded(raw), {"name": "api", "selected_operations": ["list_items"]}, set())

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"echo": "private-value"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://example.test") as client:
        store = Store(str(tmp_path / "external.db"))
        config = {"secret_keys": ["account_ref"], "header_sources": {"X-Account": "account_ref"}, "tools": {"api__list_items": {"postchecks": []}}}
        registry = Registry(client, config, {"account_ref": "private-value"}, store=store, spec_source=lambda: _return(loaded))
        await registry.load()
        assert "private-value" not in repr(registry.tools())
        assert "private-value" not in repr(store.get_spec(registry.spec_hash))
        assert await registry.call("api__list_items", {}) == {"echo": "[REDACTED]"}
        store.close()


def test_ac_107_diagnoses_ambiguous_names_refs_and_security_alternatives() -> None:
    raw = {"components": {"securitySchemes": {"bearer": {"type": "http", "scheme": "bearer"}}}, "paths": {
        "/collision": {"get": {"operationId": "collision", "parameters": [
            {"name": "same", "in": "query", "schema": {"type": "string"}},
            {"name": "same", "in": "path", "required": True, "schema": {"type": "string"}},
        ], "responses": {}}},
        "/refs": {"get": {"operationId": "refs", "parameters": [{"$ref": "other.json#/parameters/x"}], "responses": {}}},
        "/secure": {"get": {"operationId": "secure", "security": [{"bearer": []}], "responses": {}}},
    }}
    selected, errors = discover(_loaded(raw), {"name": "api", "selected_operations": ["collision", "refs", "secure"], "auth": {"type": "none"}}, {"Authorization"})
    assert selected.ops == {}
    assert {(item["operation"], item["code"]) for item in errors} == {
        ("collision", "AMBIGUOUS_PARAMETER"),
        ("refs", "EXTERNAL_REF"),
        ("secure", "UNSUPPORTED_SECURITY"),
    }


async def _return(spec: LoadedSpec) -> LoadedSpec:
    return spec


def test_ac_107_no_selection_exposes_read_only_methods_only() -> None:
    raw = {
        "paths": {
            "/a": {"get": {"operationId": "read_a", "responses": {}}, "delete": {"operationId": "delete_a", "responses": {}}},
            "/b": {"post": {"operationId": "create_b", "responses": {}}},
        }
    }
    default, _ = discover(_loaded(raw), {"name": "api"}, set())
    assert list(default.ops) == ["api__read_a"]
    written, _ = discover(_loaded(raw), {"name": "api", "selected_operations": ["delete_a"]}, set())
    assert list(written.ops) == ["api__delete_a"]
    everything, _ = discover(_loaded(raw), {"name": "api", "selected_operations": "*"}, set())
    assert sorted(everything.ops) == ["api__create_b", "api__delete_a", "api__read_a"]


async def test_ac_107_graphql_honours_selected_operations() -> None:
    from healer import gateway
    from healer.graphql_loader import operations

    def field(name: str) -> dict:
        return {"name": name, "args": [], "type": {"kind": "SCALAR", "name": "String"}}

    raw = {"data": {"__schema": {
        "queryType": {"name": "Query"}, "mutationType": {"name": "Mutation"},
        "types": [
            {"kind": "OBJECT", "name": "Query", "fields": [field("viewer"), field("secrets")]},
            {"kind": "OBJECT", "name": "Mutation", "fields": [field("deleteAll")]},
        ],
    }}}

    async def source() -> LoadedSpec:
        return LoadedSpec(raw, {f"g__{k}": v for k, v in operations(raw).items()}, "h")

    async def names(**entry) -> list[str]:
        diagnostics: list[dict] = []
        spec = await gateway._graphql_selected({"name": "g", **entry}, source, diagnostics)()
        return sorted(spec.ops), diagnostics

    assert (await names())[0] == ["g__secrets", "g__viewer"]  # default: queries only
    assert (await names(selected_operations=["viewer"]))[0] == ["g__viewer"]
    assert (await names(selected_operations=["deleteAll"]))[0] == ["g__deleteAll"]
    assert (await names(selected_operations="*"))[0] == ["g__deleteAll", "g__secrets", "g__viewer"]
    assert (await names(selected_operations=["nope"])) == ([], [{"operation": "nope", "code": "UNKNOWN_OPERATION"}])
