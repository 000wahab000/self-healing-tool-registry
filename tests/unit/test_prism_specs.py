from __future__ import annotations

import copy
import json
from pathlib import Path

import httpx
import pytest
from jsonschema import Draft202012Validator

from healer import gateway
from healer.openapi_loader import operations
from healer.store import Store

PRISM = Path(__file__).parents[2] / "demo" / "prism"


def _spec(major: int) -> dict:
    return json.loads((PRISM / f"openapi-v{major}.json").read_text())


def _published(spec: dict) -> dict:
    published = copy.deepcopy(spec)
    del published["paths"]["/openapi.json"]["get"]["responses"]["200"]["content"]["application/json"]["example"]
    return published


def test_prism_specs_are_self_published_and_expose_only_order_lookup() -> None:
    specs = [_spec(1), _spec(2)]
    for major, spec in enumerate(specs, start=1):
        assert spec["openapi"] == "3.0.3"
        assert spec["paths"]["/openapi.json"]["get"]["responses"]["200"]["content"]["application/json"]["example"] == _published(spec)
        assert spec["info"]["version"] == f"{major}.0.0"
        parsed = operations(spec)
        assert list(parsed) == ["get_order"]
        order = spec["paths"]["/orders"]["get"]
        assert order["parameters"][0]["required"] is True
        result = order["responses"]["200"]["content"]["application/json"]
        Draft202012Validator(result["schema"]).validate(result["example"])

    v1, v2 = (spec["paths"]["/orders"]["get"] for spec in specs)
    assert v1["description"] == v2["description"]
    assert v1["parameters"][0]["description"] == v2["parameters"][0]["description"]
    assert v1["parameters"][0]["name"] == "order_id"
    assert v2["parameters"][0]["name"] == "order_reference"
    assert v1["parameters"][0]["schema"] == v2["parameters"][0]["schema"]


@pytest.mark.asyncio
async def test_prism_api_registry_heals_query_rename_once(tmp_path: Path) -> None:
    active = 1
    queries: list[dict[str, str]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/openapi.json":
            return httpx.Response(200, json=_published(_spec(active)))
        query = dict(request.url.params)
        queries.append(query)
        expected = "order_id" if active == 1 else "order_reference"
        if expected not in query:
            return httpx.Response(
                422,
                headers={"content-type": "application/problem+json"},
                json={
                    "type": "https://stoplight.io/prism/errors#UNPROCESSABLE_ENTITY",
                    "title": "Invalid request",
                    "status": 422,
                    "detail": "Your request is not valid and no HTTP validation response was found in the spec, so Prism is generating this error for you.",
                    "validation": [{
                        "location": ["query"],
                        "severity": "Error",
                        "code": "required",
                        "message": f"Request query must have required property '{expected}'",
                    }],
                },
            )
        return httpx.Response(200, json={"order_id": "ORD-1001", "status": "shipped", "total": 49.95})

    api = {
        "name": "orders",
        "kind": "openapi",
        "base_url": "http://orders.example.test",
        "spec_url": "http://orders.example.test/openapi.json",
        "selected_operations": ["get_order"],
        "auth": {"type": "none"},
    }
    store = Store(str(tmp_path / "prism.db"))
    try:
        async with gateway.api_registry(api, store, {}, {}, transport=httpx.MockTransport(handle)) as registry:
            frozen_tools = copy.deepcopy(registry.tools())
            assert await registry.call("orders__get_order", {"order_id": "ORD-1001"}) == {
                "order_id": "ORD-1001", "status": "shipped", "total": 49.95
            }
            active = 2
            assert await registry.call("orders__get_order", {"order_id": "ORD-1001"}) == {
                "order_id": "ORD-1001", "status": "shipped", "total": 49.95
            }
            assert registry.tools() == frozen_tools
            assert await registry.call("orders__get_order", {"order_id": "ORD-1001"}) == {
                "order_id": "ORD-1001", "status": "shipped", "total": 49.95
            }

        assert queries == [
            {"order_id": "ORD-1001"},
            {"order_id": "ORD-1001"},
            {"order_reference": "ORD-1001"},
            {"order_reference": "ORD-1001"},
        ]
        events = store.audit_events()
        assert len(events) == 1 and events[0].outcome.value == "RECOVERED"
    finally:
        store.close()
