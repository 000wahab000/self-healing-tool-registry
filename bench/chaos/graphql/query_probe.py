import asyncio

import httpx

from healer.adapters.graphql import _query
from healer.graphql_loader import graphql_source


async def go():
    async with httpx.AsyncClient(base_url="https://countries.trevorblades.com") as c:
        spec = await graphql_source(c, "/graphql", 10)()
        for op, args in [("country",{"code":"BR"}),("continent",{"code":"EU"}),("language",{"code":"pt"}),("languages",{}),("countries",{})]:
            q=_query(op,args,spec.ops[op]); print(op, len(q), q[:400].replace("\n"," "))
            r=await c.post("/graphql",json={"query":q}); print("  ->", r.status_code, r.text[:300])
asyncio.run(go())
