"""REST adapter: send a request document (contract C1), return the raw result."""

from __future__ import annotations

import httpx


async def send(
    client: httpx.AsyncClient, doc: dict, timeout: float
) -> tuple[httpx.Response | None, Exception | None]:
    route = doc["route"]
    try:
        resp = await client.request(
            route["method"],
            route["path"],
            json=doc["body"] or None,
            params=doc["query"],
            headers=doc["header"],
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        return None, exc
    return resp, None
