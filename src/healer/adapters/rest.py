"""REST adapter: send a request document (contract C1), return the raw result."""

from __future__ import annotations

import re
from urllib.parse import quote

import httpx


async def send(
    client: httpx.AsyncClient, doc: dict, timeout: float
) -> tuple[httpx.Response | None, Exception | None]:
    route = doc["route"]
    path = route["path"]
    for name, value in doc.get("route_params", {}).items():
        if value in ("", ".", ".."):
            return None, ValueError("invalid route parameter")
        path = path.replace("{" + name + "}", quote(str(value), safe=""))
    if re.search(r"\{[^{}]+\}", path):
        return None, ValueError("missing route parameter")
    if not path.startswith("/") or path.startswith("//") or "://" in path:
        return None, ValueError("invalid route")
    try:
        headers = dict(doc["header"])
        headers.setdefault("authorization", "")
        headers.setdefault("cookie", "")
        resp = await client.request(
            route["method"],
            path,
            json=doc["body"] or None,
            params=doc["query"],
            headers=headers,
            timeout=timeout,
            auth=None,
        )
    except httpx.HTTPError as exc:
        return None, exc
    return resp, None
