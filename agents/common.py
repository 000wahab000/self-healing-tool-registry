"""Shared agent pieces: prompt, task, LLM, tool factory and the run loop."""

from __future__ import annotations

import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.errors import GraphRecursionError

from healer.models import ErrorClass

SYSTEM_PROMPT = (
    "You are an operations assistant. Complete the user's task by calling the provided tools, "
    "then reply with a one-line summary of what was done. "
    'If a tool result has "retry": false, do not call that tool again with the same arguments. '
    'If its error is "SCHEMA_DRIFT_UNRECOVERABLE", the tool is unavailable for the rest of this '
    "task: do not call it again, report it as skipped and continue with the rest of the task."
)
TASK = (
    "Look up user 123, change their email to ada.new@example.com, set their manager to 456, "
    "and open a support ticket titled 'Email changed' confirming the change."
)
MAX_ITERATIONS = 10

# (tool name, args) -> (text returned to the LLM, class to log)
Execute = Callable[[str, dict], Awaitable[tuple[str, ErrorClass]]]


def make_llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=os.environ["NVIDIA_API_KEY"],
        model=os.environ.get("LLM_MODEL", "openai/gpt-oss-20b"),
        temperature=0,
    )


def make_tools(
    registry, execute: Execute, agent: str, store, run_id: str
) -> list[StructuredTool]:
    """One tool per registry spec; both agents differ only in `execute`. Logs each call."""

    def tool(spec: dict) -> StructuredTool:
        async def invoke(**args) -> str:
            t0 = time.perf_counter()
            text, cls = await execute(spec["name"], args)
            if store:
                ms = round((time.perf_counter() - t0) * 1000)
                store.log_call(agent, run_id, spec["name"], cls, ms)
            return text

        return StructuredTool(
            name=spec["name"],
            description=spec["description"],
            args_schema=spec["parameters"],
            coroutine=invoke,
        )

    return [tool(spec) for spec in registry.tools()]


@dataclass
class RunResult:
    final_text: str
    tool_calls: int
    llm_tokens: int
    hit_limit: bool
    error: str | None


async def run(agent, task: str) -> RunResult:
    messages, hit_limit, error = [], False, None
    try:
        # Stream full states so the messages produced so far survive a recursion-limit error.
        async for state in agent.astream(
            {"messages": [("user", task)]},
            {"recursion_limit": 2 * MAX_ITERATIONS + 1},
            stream_mode="values",
        ):
            messages = state["messages"]
    except GraphRecursionError:
        hit_limit = True
    # A failed LLM or tool call is a result for the benchmark to record, not a crash.
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
    ai = [m for m in messages if isinstance(m, AIMessage)]
    return RunResult(
        final_text=ai[-1].text if ai else "",
        tool_calls=sum(isinstance(m, ToolMessage) for m in messages),
        llm_tokens=sum((m.usage_metadata or {}).get("total_tokens", 0) for m in ai),
        hit_limit=hit_limit,
        error=error,
    )
