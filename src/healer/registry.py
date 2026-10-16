"""Tool registry: one frozen agent-facing schema per operation, and the call pipeline."""

from __future__ import annotations

import asyncio
import copy
import time
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, replace

import httpx
from jsonschema import Draft202012Validator, validators

from healer import contract, detect, retry
from healer.adapters import rest
from healer.heal import Healer, api_error
from healer.jev import JevClient
from healer.models import ErrorClass, Fix, Outcome, SpecSource
from healer.openapi_loader import openapi_source
from healer.ops import apply_ops
from healer.settings import HEAL_DEADLINE_S, REQUEST_TIMEOUT_S, SPEC_MODE
from healer.store import FixStore

# FR-3.4: value rules are the API's to enforce, so a rejected value reaches it and comes back
# as BUSINESS. Argument pre-validation (FR-2.1) checks structure and types only.
_VALUE_RULES = {
    "pattern",
    "enum",
    "const",
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minItems",
    "maxItems",
}
ArgumentValidator = validators.extend(
    Draft202012Validator, dict.fromkeys(_VALUE_RULES, lambda *_: ())
)


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
        store: FixStore | None = None,
        jev: JevClient | None = None,
        *,
        clock: Callable[[], float] = time.perf_counter,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[], float] = retry.random_jitter,
        spec_mode: str = SPEC_MODE,
        spec_source: SpecSource | None = None,
        grpc_channel: object | None = None,
    ) -> None:
        if spec_mode not in (
            "on",
            "off",
        ):  # a typo must not silently run the wrong ablation arm
            raise ValueError(f"spec_mode must be 'on' or 'off', not {spec_mode!r}")
        self.client = client
        self.tools_config = tools_config
        self.cfg = cfg
        self.store = store
        self.grpc_channel = grpc_channel
        if spec_source is not None:
            self.spec_source = spec_source
        elif grpc_channel is not None:
            from healer.grpc_loader import grpc_source

            self.spec_source = grpc_source(grpc_channel)
        else:
            self.spec_source = openapi_source(client)
        self.grpc_source = self.spec_source if grpc_channel is not None else None
        self.defs: dict[str, ToolDefinition] = {}
        self.spec_hash = ""
        self._clock, self._sleep, self._jitter = clock, sleep, jitter
        # Healing needs somewhere to keep fixes and the audit log; without a store, errors pass through.
        self.healer = (
            Healer(
                store=store,
                jev=jev,
                spec_source=self.spec_source,
                cfg=cfg,
                header_sources=tools_config.get("header_sources", {}),
                attempt=self._attempt,
                clock=clock,
                spec_mode=spec_mode,
                tools=lambda: list(self.defs.values()),
            )
            if store
            else None
        )

    async def load(self) -> None:
        spec = await self.spec_source()
        ops, self.spec_hash = spec.ops, spec.spec_hash
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
            self.store.save_spec(self.spec_hash, spec.raw)

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
        if op["method"] == "GRAPHQL":
            # The adapter uses this name to select the current introspected operation.
            doc["operation"] = op["operation_id"]
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
        route: dict | None = None,
    ) -> Outcome:
        """Send `base` through `fix` (request ops, response ops), classify, check the contract.
        `route` replaces the sent route after the ops (a tool's `preverify` dry run)."""
        doc = apply_ops(fix.request_ops, base, self.cfg) if fix else base
        if route:
            doc = {**doc, "route": route}
        protocol = tool.base_op["method"]
        if protocol == "GRAPHQL":
            from healer.adapters import graphql

            outcome = await graphql.send(
                self.client, doc, timeout, spec_source=self.spec_source
            )
        elif protocol == "GRPC":
            from healer.adapters import grpc
            from healer.grpc_loader import _pool, message_class

            if self.grpc_source is None:
                return contract.check(
                    Outcome(ErrorClass.E1, "grpc", "REFLECTION_UNAVAILABLE"),
                    output_schema=tool.output_schema,
                    postchecks=tool.config["postchecks"],
                    base_doc=base,
                )
            try:
                latest = await self.grpc_source()
                service, method_name = tool.base_op["operation_id"].rsplit(".", 1)
                pool = _pool([bytes.fromhex(item) for item in latest.raw["descriptors"]])
                method = pool.FindServiceByName(service).methods_by_name[method_name]
                outcome = await grpc.send(
                    self.grpc_channel,
                    doc,
                    timeout,
                    message_class(pool, method.input_type.full_name),
                    message_class(pool, method.output_type.full_name),
                )
            except (ValueError, KeyError, TypeError):
                # Reflection and descriptor failures are transport failures, not leaked details.
                outcome = Outcome(ErrorClass.E1, "grpc", "REFLECTION_UNAVAILABLE")
        else:
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

    async def call(self, name: str, args: dict) -> dict:
        tool = self.defs.get(name)
        if tool is None:
            return {"error": "UNKNOWN_TOOL", "tool": name, "retry": False}
        if not ArgumentValidator(tool.agent_schema).is_valid(args):
            return {"error": "AGENT_ARG_ERROR", "tool": name, "retry": False}
        t0 = self._clock()
        base = self.base_doc(tool, args)
        outcome = await retry.with_retries(
            lambda: self._attempt(tool, base, tool.active_fix),
            remaining=lambda: HEAL_DEADLINE_S - (self._clock() - t0),
            sleep=self._sleep,
            jitter=self._jitter,
        )
        if outcome.cls is ErrorClass.OK:
            return outcome.data
        if outcome.cls in (ErrorClass.BUSINESS, ErrorClass.E1) or self.healer is None:
            return api_error(outcome)
        return await self.healer.heal(tool, base, outcome, t0)
