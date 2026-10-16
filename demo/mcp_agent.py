"""Demo agent: one task over two upstream MCP servers, through the healer front door only.

    python -m demo.mcp_agent             # scripted: fixed call sequence, no API key
    python -m demo.mcp_agent --llm       # LangGraph agent on NVIDIA NIM (needs NVIDIA_API_KEY)

The agent launches `python -m healer.mcp_server --mcp-servers demo/mcp_servers.demo.json --no-rest`
as a stdio subprocess and never talks to the upstream servers. The demo config starts the `users`
upstream with `--drift M1 --drift-after 1`: after its first call the argument `user_id` is renamed
to `customer_id`, so the second `users__get_user` call hits drift mid-task and the front door heals
it. Run from the repository root. Afterwards the audit rows are read from `--db` (default
`demo/demo.db`) because the front door exposes no audit tool.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from healer.store import Store

ROOT = Path(__file__).resolve().parent.parent
DEMO_CONFIG = "demo/mcp_servers.demo.json"
DEMO_DB = "demo/demo.db"
TASK = (
    "Look up user 123, then open a ticket for them in the tickets system titled 'Email check', "
    "list their tickets, and finally look up user 123 again to confirm their email."
)
SCRIPT: list[tuple[str, dict]] = [
    ("users__get_user", {"user_id": "123"}),
    ("tickets__create_ticket", {"user_id": "123", "title": "Email check"}),
    ("tickets__list_tickets", {"user_id": "123"}),
    ("users__get_user", {"user_id": "123"}),  # the users upstream has drifted by now
]


class Transcript:
    """Calls the front door, prints each call, and notes heals read from the shared audit db."""

    def __init__(self, session: ClientSession, db: str) -> None:
        self.session, self.db = session, db
        self.calls = 0
        self.errors = 0
        self._seen = 0

    async def call(self, name: str, args: dict) -> tuple[str, bool]:
        res = await self.session.call_tool(name, args)
        text = "".join(c.text for c in res.content if getattr(c, "type", "") == "text")
        self.calls += 1
        self.errors += bool(res.is_error)
        print(f"  call  {name} {json.dumps(args)}")
        print(f"  ->    {'ERROR ' if res.is_error else ''}{text}")
        for ev in self._new_audit():
            print(
                f"  heal  {ev.tool}: {ev.outcome.value} (tier {ev.tier.name}, {ev.heal_ms} ms)"
            )
        return text, bool(res.is_error)

    def _new_audit(self) -> list:
        store = Store(self.db)
        try:
            rows = store.audit_events()
        finally:
            store.close()
        new, self._seen = rows[self._seen :], len(rows)
        return new


async def run_scripted(t: Transcript) -> str:
    for name, args in SCRIPT:
        await t.call(name, args)
    return "scripted sequence finished"


async def run_llm(t: Transcript, tools: list) -> str:
    """LangGraph ReAct agent whose tools are the front door's tools (same shape as agents/)."""
    from langchain_core.tools import StructuredTool
    from langgraph.prebuilt import create_react_agent

    from agents.common import SYSTEM_PROMPT, make_llm, run

    def wrap(tool) -> StructuredTool:
        async def invoke(**args) -> str:
            text, _ = await t.call(tool.name, args)
            return text

        return StructuredTool(
            name=tool.name,
            description=tool.description or "",
            args_schema=tool.input_schema,
            coroutine=invoke,
        )

    agent = create_react_agent(
        make_llm(), [wrap(x) for x in tools], prompt=SYSTEM_PROMPT
    )
    result = await run(agent, TASK)
    if result.error:
        raise RuntimeError(result.error)
    return result.final_text


async def run_demo(
    mode: str = "scripted", db: str = DEMO_DB, config: str = DEMO_CONFIG
) -> dict:
    """Run the task once; returns calls, errors seen by the agent and the audit rows."""
    for suffix in ("", "-wal", "-shm"):
        Path(str(ROOT / db) + suffix).unlink(missing_ok=True)
    params = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "healer.mcp_server",
            "--mcp-servers",
            config,
            "--no-rest",
            "--db",
            db,
        ],
        env=dict(os.environ),
        cwd=str(ROOT),
    )
    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = (await session.list_tools()).tools
        print(f"Tools from the front door: {', '.join(x.name for x in tools)}")
        print(f"Task: {TASK}\n")
        t = Transcript(session, str(ROOT / db))
        summary = await (run_scripted(t) if mode == "scripted" else run_llm(t, tools))
    store = Store(str(ROOT / db))
    try:
        audit = store.audit_events()
    finally:
        store.close()
    print(f"\n{summary}: {t.calls} tool calls, {t.errors} errors seen by the agent")
    print(f"Audit log ({len(audit)} rows):")
    for ev in audit:
        print(
            f"  {ev.tool}: {ev.outcome.value} class={ev.cls.value} tier={ev.tier.name}"
        )
    return {"calls": t.calls, "errors": t.errors, "audit": audit}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--scripted", action="store_true", help="fixed call sequence (default)"
    )
    mode.add_argument(
        "--llm", action="store_true", help="LangGraph agent on NVIDIA NIM"
    )
    parser.add_argument("--db", default=DEMO_DB)
    parser.add_argument("--config", default=DEMO_CONFIG)
    args = parser.parse_args()
    asyncio.run(run_demo("llm" if args.llm else "scripted", args.db, args.config))


if __name__ == "__main__":
    main()
