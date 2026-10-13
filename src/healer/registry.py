"""Tool registry: one frozen agent-facing schema per operation, and the call pipeline."""

from __future__ import annotations

import copy
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, replace

import httpx
from jsonschema import Draft202012Validator

from healer import contract, detect
from healer.adapters import rest
from healer.models import ErrorClass, Fix, Outcome
from healer.openapi_loader import fetch_spec, operations
from healer.ops import apply_ops
from healer.settings import REQUEST_TIMEOUT_S
from healer.store import Store


@dataclass
class ToolDefinition:
    name: str
    base_op: dict  # never mutated after load
    agent_schema: dict  # never mutated after load
    output_schema: dict | None
    wire_op: dict
    config: dict
    version: int = 1
    active_fix: Fix | None = None


def _agent_schema(op: dict) -> dict:
    # ponytail: body properties and query params only; path/cookie params are not exposed.
    body = op["body_schema"] or {}
    props = dict(body.get("properties", {}))
    required = list(body.get("required", []))
    for p in op["params"]:
        if p["in"] != "query":
            continue
        desc = {"description": p["description"]} if p["description"] else {}
        props[p["name"]] = {**p["schema"], **desc}
        if p["required"]:
            required.append(p["name"])
    return copy.deepcopy({"type": "object", "properties": props, "required": required})


class Registry:
    def __init__(
        self,
        client: httpx.AsyncClient,
        tools_config: dict,
        cfg: Mapping[str, str],
        store: Store | None = None,
    ) -> None:
        self.client = client
        self.tools_config = tools_config
        self.cfg = cfg
        self.store = store
        self.defs: dict[str, ToolDefinition] = {}
        self.spec_hash = ""

    async def load(self) -> None:
        spec, self.spec_hash = await fetch_spec(self.client)
        ops = operations(spec)
        self.defs = {
            name: ToolDefinition(
                name=name,
                base_op=ops[name],
                agent_schema=_agent_schema(ops[name]),
                output_schema=ops[name]["response_schema"],
                wire_op=copy.deepcopy(ops[name]),
                config=config,
            )
            for name, config in self.tools_config["tools"].items()
        }
        if self.store:
            self.store.save_spec(self.spec_hash, spec)

    def tools(self) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.base_op["description"],
                "parameters": t.agent_schema,
            }
            for t in self.defs.values()
        ]

    def base_doc(self, tool: ToolDefinition, args: dict) -> dict:
        op = tool.base_op
        query = {p["name"] for p in op["params"] if p["in"] == "query"}
        doc = {
            "route": {"method": op["method"], "path": op["path"]},
            "body": {k: v for k, v in args.items() if k not in query},
            "query": {k: v for k, v in args.items() if k in query},
            "header": {},
        }
        if tool.config.get("idempotency_key"):
            doc["header"]["idempotency-key"] = (
                uuid.uuid4().hex
            )  # one per call; replays reuse it
        return copy.deepcopy(doc)

    async def _attempt(
        self,
        tool: ToolDefinition,
        base: dict,
        fix: Fix | None,
        timeout: float = REQUEST_TIMEOUT_S,
    ) -> Outcome:
        """Send `base` through `fix` (request ops, response ops), classify, check the contract."""
        doc = apply_ops(fix.request_ops, base, self.cfg) if fix else base
        resp, exc = await rest.send(self.client, doc, timeout)
        outcome = detect.classify(resp, exc)
        if fix and outcome.cls is ErrorClass.OK:
            outcome = replace(
                outcome, data=apply_ops(fix.response_ops, outcome.data, self.cfg)
            )
        return contract.check(
            outcome,
            output_schema=tool.output_schema,
            postchecks=tool.config["postchecks"],
            base_doc=base,
        )

    @staticmethod
    def _api_error(outcome: Outcome) -> dict:
        return {
            "error": "API_ERROR",
            "class": outcome.cls.value,
            "status": outcome.raw_code,
            "detail": outcome.data,
        }

    async def call(self, name: str, args: dict) -> dict:
        tool = self.defs.get(name)
        if tool is None:
            return {"error": "UNKNOWN_TOOL", "tool": name, "retry": False}
        if not Draft202012Validator(tool.agent_schema).is_valid(args):
            return {"error": "AGENT_ARG_ERROR", "tool": name, "retry": False}
        base = self.base_doc(tool, args)
        outcome = await self._attempt(tool, base, tool.active_fix)
        return (
            outcome.data if outcome.cls is ErrorClass.OK else self._api_error(outcome)
        )
