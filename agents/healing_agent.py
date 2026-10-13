"""Healing agent: every tool call goes through the self-healing `Registry`."""

from __future__ import annotations

import json

from langgraph.prebuilt import create_react_agent

from agents.common import SYSTEM_PROMPT, make_tools
from healer.models import ErrorClass


def build(registry, llm, store=None, run_id=""):
    async def execute(name: str, args: dict) -> tuple[str, ErrorClass]:
        result = await registry.call(name, args)
        # ponytail: a successful payload that itself has an "error" key would be logged as an error.
        if "error" not in result:
            return json.dumps(result), ErrorClass.OK
        # AGENT_ARG_ERROR / UNKNOWN_TOOL carry no class; call_events only allows ErrorClass values.
        cls = ErrorClass(result["class"]) if "class" in result else ErrorClass.BUSINESS
        return json.dumps(result), cls

    tools = make_tools(registry, execute, "healing", store, run_id)
    return create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)
