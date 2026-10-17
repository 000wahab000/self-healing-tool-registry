"""Direct probe of healer.adapters.graphql.send against the live Countries API (read-only, no LLM).
Shows two adapter defects independent of the gateway: (1) spec keys namespaced as the gateway does ->
every argument is 'unknown'; (2) schema without a mutationType (null) -> AttributeError."""
import asyncio

import httpx

from healer.adapters import graphql
from healer.graphql_loader import graphql_source
from healer.models import LoadedSpec


async def go():
    async with httpx.AsyncClient(base_url="https://countries.trevorblades.com") as c:
        plain = await graphql_source(c, "/graphql", 10)()
        pref = LoadedSpec(plain.raw, {"ctry__" + k: v for k, v in plain.ops.items()}, plain.spec_hash)

        async def src_plain():
            return plain

        async def src_pref():
            return pref
        doc = {"operation": "language", "variables": {"code": "pt"}, "route": {"path": "/graphql"}}
        for label, src in (("unprefixed spec keys", src_plain), ("namespaced spec keys (as gateway apis)", src_pref)):
            try:
                o = await graphql.send(c, dict(doc), 10, spec_source=src)
                print(label, "->", repr(o)[:260])
            except Exception as e:  # noqa: BLE001
                print(label, "-> EXCEPTION", type(e).__name__, e)

asyncio.run(go())
