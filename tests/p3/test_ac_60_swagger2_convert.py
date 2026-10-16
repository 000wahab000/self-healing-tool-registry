"""AC-60 (FR-22.1): the Swagger 2.0 fixture converts to the mock's OpenAPI 3 operations exactly."""

from __future__ import annotations

import json
from pathlib import Path

from healer.openapi_loader import operations, resolve_refs
from healer.swagger2 import convert

FIXTURES = Path(__file__).parents[2] / "mock_api" / "fixtures"


def test_ac_60_fixture_is_a_swagger_2_document() -> None:
    doc = json.loads((FIXTURES / "swagger2.json").read_text())
    assert doc["swagger"] == "2.0"
    assert "definitions" in doc and "components" not in doc


async def test_ac_60_swagger2_fixture_matches_the_openapi3_document(client) -> None:
    doc = json.loads((FIXTURES / "swagger2.json").read_text())
    live = (await client.get("/openapi.json")).json()
    assert operations(resolve_refs(convert(doc))) == operations(resolve_refs(live))
