"""Jev Client (FR-8): one Choice call that selects a candidate index.

Jev never produces operations or values (AGENTS.md § Coding rules); it only picks one of ours.
"""

from __future__ import annotations

import os
import string
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import httpx

from healer.canonical import dumps
from healer.settings import JEV_TIMEOUT_S

_TYPES = {
    bool: "bool",
    int: "int",
    float: "float",
    str: "str",
    list: "arr",
    dict: "obj",
    type(None): "null",
}
_OPS: dict[str, Callable[[dict], str]] = {
    "move": lambda o: f"move {_dotted(o['from'])} -> {_dotted(o['to'])}",
    "cast": lambda o: f"cast {_dotted(o['path'])} to {o['to']}",
    # Config key only: the value is a secret and never leaves the process.
    "header": lambda o: f"header {o['name']} from config {o['src']['key']}",
    "route": lambda o: f"route {o['method']} {o['path']}",
    "enum_map": lambda o: f"map values of {_dotted(o['path'])} {o['mapping']}",
    "encoding": lambda o: f"send as {o['content_type']}",
}


class JevUnavailable(Exception):
    """Timeout, transport or HTTP error, or an answer that is not one of our options."""


@dataclass
class JevChoice:
    index: int
    confidence: float
    tokens: int


class JevClient:
    def __init__(
        self,
        api_key: str | None,
        client: httpx.AsyncClient | None = None,
        model: str = "jev-latest",
        url: str = "https://api.typesafe.ai/v1/systemone",
        session_header: bool = False,
    ) -> None:
        self._key = api_key
        self._owned = client is None
        self._client = client  # created on first use: no idle client when Jev is never asked
        self._model = model
        self._url = url
        self._session_header = session_header

    async def aclose(self) -> None:
        if self._owned and self._client is not None:
            await self._client.aclose()

    async def choose(self, state: str, question: str, options: list[str]) -> JevChoice:
        # ponytail: labels run A-Z, so at most 26 options; MAX_CANDIDATES is 8.
        labels = list(string.ascii_uppercase[: len(options)])
        body = {
            "model": self._model,
            "state": state,
            "questions": {
                "fix": {
                    "type": "choice",
                    "instructions": question,
                    "criteria": dict(zip(labels, options)),
                }
            },
        }
        if self._client is None:
            self._client = httpx.AsyncClient()
        try:
            headers = {}
            if self._key:
                headers["Authorization"] = f"Bearer {self._key}"
            if self._session_header:
                headers["x-opencode-session"] = str(uuid.uuid4())
            response = await self._client.post(
                self._url,
                json=body,
                headers=headers,
                timeout=JEV_TIMEOUT_S,
            )
            response.raise_for_status()
            data = response.json()
            answer = data["answers"]["fix"]
            index = labels.index(answer["choice"])
            confidence = float(answer["confidence"])
            usage = data.get("usage") or {}
            tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            # Also rejects NaN, which would slip past any `confidence < threshold` check.
            if not 0 <= confidence <= 1:
                raise ValueError(confidence)
        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
        ) as exc:
            raise JevUnavailable from exc
        return JevChoice(index, confidence, tokens)


def _dotted(path: list[str | int]) -> str:
    return ".".join(map(str, path))


def _arg_types(node: dict, prefix: list[str]) -> Iterator[str]:
    """`path: type` for each leaf of the agent's arguments. Values are PII-prone and never read."""
    for key in sorted(node):
        value = node[key]
        if isinstance(value, dict):
            yield from _arg_types(value, [*prefix, key])
        else:
            yield f"{_dotted([*prefix, key])}: {_TYPES.get(type(value), 'obj')}"


def _entry(e: dict[str, Any]) -> str:
    if e["change"] == "route_changed":
        return f"route_changed {e['side']} {e['method']} {e['path']}"
    parts = [e["change"], e["side"], _dotted(e["path"]), e["type"]]
    if "old_type" in e:
        parts.append(f"(was {e['old_type']})")
    parts.append("required" if e["required"] else "optional")
    if e.get("description"):
        parts.append(dumps(e["description"]))
    return " ".join(parts)


def render_state(entries: list[dict], base_doc: dict) -> str:
    args = [
        line
        for loc in ("body", "query")
        for line in _arg_types(base_doc.get(loc, {}), [loc])
    ]
    return "\n".join(
        ["spec diff:", *map(_entry, entries), "agent arguments (types only):", *args]
    )


def render_option(fix: dict) -> str:
    ops = [("req", o) for o in fix["request_ops"]] + [
        ("resp", o) for o in fix["response_ops"]
    ]
    return "; ".join(f"{side} {_OPS[o['op']](o)}" for side, o in ops)


def from_env(env=None) -> JevClient | None:
    """Prefer TypeSafe direct, then OpenRouter, then opt-in OpenCode free Jev."""
    env = os.environ if env is None else env
    if key := env.get("JEV_API_KEY"):
        extra = {
            k: env[v]
            for k, v in (("url", "JEV_URL"), ("model", "JEV_MODEL"))
            if env.get(v)
        }
        return JevClient(key, **extra)
    if key := env.get("OPENROUTER_API_KEY"):
        return JevClient(
            key,
            url="https://openrouter.ai/api/v1/systemone",
            model="~typesafe/jev-latest",
        )
    if env.get("OPENCODE_JEV_FREE") == "1":
        return JevClient(
            None,
            url="https://opencode.ai/inference/systemone/v1/systemone",
            model="jev-1.13-free",
            session_header=True,
        )
    return None
