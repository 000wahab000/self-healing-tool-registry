"""Baseline agent: same tools, but each call is a bare v1 HTTP request. No healing, no retries."""

from __future__ import annotations

import httpx
from langgraph.prebuilt import create_react_agent

from agents.common import SYSTEM_PROMPT, make_tools
from healer import detect
from healer.models import ErrorClass
from healer.settings import REQUEST_TIMEOUT_S


def build(client, registry, llm, store=None, run_id=""):
    async def execute(name: str, args: dict) -> tuple[str, ErrorClass]:
        op = registry.defs[name].base_op  # registry is used only for the v1 specs
        try:
            resp = await client.request(
                op["method"], op["path"], json=args, timeout=REQUEST_TIMEOUT_S
            )
        except httpx.HTTPError as exc:
            return f"HTTP error: {type(exc).__name__}", detect.classify(None, exc).cls
        return f"HTTP {resp.status_code}: {resp.text}", detect.classify(resp).cls

    tools = make_tools(registry, execute, "baseline", store, run_id)
    return create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)
