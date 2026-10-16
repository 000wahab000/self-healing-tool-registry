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
        headers = {name.casefold(): value for name, value in doc["header"].items()}
        request = client.build_request(
            route["method"],
            path,
            json=doc["body"] or None,
            params=doc["query"],
            headers=headers,
            timeout=timeout,
        )
        # Client-level credentials are never inherited; only the document's headers authenticate.
        for name in ("authorization", "cookie"):
            if name not in headers:
                request.headers.pop(name, None)
        resp = await client.send(request, auth=None)
    except (httpx.HTTPError, ValueError) as exc:
        # ValueError: the pinned transport refused the destination (egress, rebinding, DNS).
        return None, exc
    return resp, None
