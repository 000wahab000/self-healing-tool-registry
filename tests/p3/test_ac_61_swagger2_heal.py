"""AC-61 (FR-22.2): the registry heals M1 when its base spec is the Swagger 2.0 fixture."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from healer.models import DecisionPath, HealOutcome
from healer.openapi_loader import openapi_source
from healer.swagger2 import swagger2_source

FIXTURES = Path(__file__).parents[2] / "mock_api" / "fixtures"

USER = {"id": "123", "name": "Ada", "email": "ada@example.com"}
GET_USER = {"user_id": "123"}


async def test_ac_61_swagger2_fixture_heals_m1(api, client, store, make_registry):
    doc = json.loads((FIXTURES / "swagger2.json").read_text())
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=doc))

    async with httpx.AsyncClient(
        transport=transport, base_url="http://spec"
    ) as spec_client:
        base = swagger2_source(spec_client, "/swagger.json")
        live = openapi_source(client)
        fetches = 0

        async def source():
            nonlocal fetches
            fetches += 1
            return await (base() if fetches == 1 else live())

        reg = await make_registry(spec_source=source)
        assert fetches == 1  # the base spec was loaded through the 2.0 fixture

        api.set_mutation("M1")
        assert await reg.call("get_user", GET_USER) == USER
        assert fetches == 2  # diagnosis read the mock's current (mutated) document

    (heal,) = store.audit_events()
    assert (heal.outcome, heal.path) == (HealOutcome.RECOVERED, DecisionPath.diff)
