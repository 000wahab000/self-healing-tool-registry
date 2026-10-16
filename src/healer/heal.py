"""Heal Controller (FR-10, FR-11): at most one heal attempt per failed call, one audit event per attempt."""

from __future__ import annotations

import asyncio
import copy
import logging
import re
import sqlite3
import time
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

import httpx

from healer import (
    candidates,
    canonical,
    contract,
    detect,
    diagnose,
    fingerprint,
    safety,
)
from healer import repair as repair_agent
from healer.adapters import rest
from healer.detect import VALUE_KINDS
from healer.jev import JevClient, JevUnavailable, render_option, render_state
from healer.models import (
    AuditEvent,
    DecisionPath,
    ErrorClass,
    Fix,
    FixStatus,
    HealError,
    HealOutcome,
    LoadedSpec,
    Outcome,
    Reason,
    Side,
    SpecSource,
    Tier,
    Violation,
)
from healer.ops import OpError, apply_ops
from healer.settings import HEAL_DEADLINE_S, REPLAY_TIMEOUT_MAX_S, SPEC_MODE
from healer.store import FixStore, redact_value, sanitize
from healer.verify import Verifier

if TYPE_CHECKING:
    from healer.registry import ToolDefinition

QUESTION = (
    "Which candidate fix correctly adapts the agent's request to the changed API?"
)
# Tier-1 refusals the repair agent may still fix (FR-17.15). Never NO_SAFE_VALUE (a value the
# agent did not send would have to be invented), NOT_DRIFT, KNOWN_UNFIXABLE, DEADLINE or
# anything after a write.
REPAIRABLE = frozenset(
    {Reason.NO_CANDIDATE, Reason.LOW_CONFIDENCE, Reason.UNSAFE_PATCH, Reason.VERIFY_FAILED}
)
TRIAGE_QUESTION = (
    "A deterministic healer refused this failed tool call. Should a repair agent try to adapt "
    "the agent's own arguments to the changed API, or should the error go back to the agent?"
)
TRIAGE_OPTIONS = (
    "repair: the API's shape changed and the agent's existing arguments can be re-mapped to it",
    "report: the agent sent a bad or missing value, or the API refused for a business reason",
)
# FR-11.3: these abort reasons make the fingerprint KNOWN_UNFIXABLE for the next 60 s.
NEGATIVE = frozenset(
    {
        Reason.VERIFY_FAILED,
        Reason.POSTCHECK_FAILED_AFTER_WRITE,
        Reason.NO_CANDIDATE,
        Reason.NO_SAFE_VALUE,
        Reason.LOW_CONFIDENCE,
        Reason.UNSAFE_PATCH,
        Reason.UNSAFE_REPLAY,
        Reason.UNSUPPORTED_CLASS,
    }
)
AUDIT_OUTCOME = {
    Reason.NOT_DRIFT: HealOutcome.NOT_DRIFT,
    Reason.VERIFY_FAILED: HealOutcome.VERIFY_FAILED,
    Reason.POSTCHECK_FAILED_AFTER_WRITE: HealOutcome.VERIFY_FAILED,
}


def _layer_reason(detail: str) -> Reason:
    if detail == Reason.UNSAFE_REPLAY.value:
        return Reason.UNSAFE_REPLAY
    return Reason.UNSAFE_PATCH


def api_error(outcome: Outcome) -> dict:
    return {
        "error": "API_ERROR",
        "class": outcome.cls.value,
        "status": outcome.raw_code,
        "detail": outcome.data,
    }


class _Abort(OpError):
    """Ends the heal with a reason. An OpError from the interpreter ends it the same way."""


@dataclass
class _Heal:
    tool: ToolDefinition
    base: dict
    outcome: Outcome
    t0: float  # the call started: the deadline counts from here
    detected: float  # the failing response arrived: heal_ms and mttr_ms count from here
    fp: str = ""
    signature: dict = field(default_factory=dict)
    tier: Tier = Tier.T1
    path: DecisionPath | None = None
    fix_id: int | None = None
    jev_tokens: int = 0
    llm_tokens: int = 0  # the tier-2 repair agent's tokens
    deadline: asyncio.Timeout | None = None
    waiter: bool = False  # single-flight follower: writes no audit event
    ops: dict | None = None  # operations of the current spec; None in clue mode
    new_op: dict | None = None
    entries: list[dict] = field(default_factory=list)
    schema_hash: str = ""
    transient: bool = False  # the replay hit E1
    needs_preverify: bool = False  # a Jev pick on a write tool (FR-8.6)
    layers: list[dict[str, str]] = field(default_factory=list)
    replay_attempted: bool = False


class Healer:
    def __init__(
        self,
        *,
        store: FixStore,
        jev: JevClient | None,
        spec_source: SpecSource,
        cfg: Mapping[str, str],
        header_sources: Mapping[str, str],
        attempt: Callable[..., Awaitable[Outcome]],
        clock: Callable[[], float],
        spec_mode: str = SPEC_MODE,
        tools: Callable[[], Iterable[ToolDefinition]] | None = None,
        repair: repair_agent.RepairAgent | None = None,
        secret_values: Iterable[str] | None = None,
    ) -> None:
        self._store, self._jev, self._spec_source = store, jev, spec_source
        self._spec_mode = spec_mode
        self._cfg, self._header_sources = cfg, header_sources
        inferred_secrets = tuple(
            value
            for key, value in cfg.items()
            if re.search(
                r"authorization|token|secret|password|"
                r"(?:api|client|access|auth|refresh)[-_]?key|cookie|credential",
                key,
                re.IGNORECASE,
            )
        )
        self._secrets = (
            tuple(secret_values) if secret_values is not None else inferred_secrets
        )
        self._attempt, self._clock = attempt, clock
        self._client = getattr(getattr(attempt, "__self__", None), "client", None)
        self._tools = tools
        self._repair = repair
        self._verifier = Verifier()
        self._flights: dict[str, asyncio.Future[Reason | None]] = {}
        self._saved_specs: set[str] = set()
        # fingerprint -> when its first failing response arrived, until a heal recovers it.
        # ponytail: never-recovered fingerprints stay (bounded by the distinct breaks seen).
        self._first_seen: dict[str, float] = {}

    async def heal(
        self, tool: ToolDefinition, base: dict, outcome: Outcome, t0: float
    ) -> Any:
        """The agent's result: data when recovered, an error dict otherwise."""
        h = _Heal(tool, base, outcome, t0, self._clock())
        h.layers = [
            {"layer": f"L{i}", "name": name, "status": "skip", "detail": "not_reached"}
            for i, name in enumerate(("safety", "request_schema", "response_schema",
                "postchecks", "readback", "invariants", "replay_safety"), 1)
        ]
        h.fp, h.signature = fingerprint.fingerprint(tool.name, outcome)
        try:
            async with asyncio.timeout(
                HEAL_DEADLINE_S - (self._clock() - t0)
            ) as h.deadline:
                return await self._run(h)
        except TimeoutError:
            reason = Reason.DEADLINE
        except OpError as e:
            reason = e.reason
        except Exception as e:  # noqa: BLE001 - every failed heal still gets one audit row
            logging.getLogger(__name__).error(
                "heal failed for %s: %s", tool.name, sanitize(str(e), self._secrets)
            )
            reason = Reason.VERIFY_FAILED
        return self._abort(h, reason)

    async def _run(self, h: _Heal) -> Any:
        if h.outcome.cls is ErrorClass.E6:
            # Its fingerprint carries the diff signature, so the spec comes first.
            await self._diagnose(h)
            diff_signature = (
                diagnose.diff_signature(h.entries) if h.ops is not None else None
            )
            h.fp, h.signature = fingerprint.fingerprint(
                h.tool.name, h.outcome, diff_signature
            )
        if self._store.is_negative(h.fp):
            h.tier, h.path = Tier.T0, DecisionPath.cache
            raise _Abort(Reason.KNOWN_UNFIXABLE)
        if h.fp in self._flights:
            return await self._follow(h, self._flights[h.fp])
        flight = self._flights[h.fp] = asyncio.get_running_loop().create_future()
        verdict: Reason | None = Reason.DEADLINE  # what a cancellation means
        try:
            data = await self._lead(h)
            verdict = None
            return data
        except OpError as e:
            verdict = e.reason
            raise
        finally:
            del self._flights[h.fp]
            flight.set_result(verdict)

    async def _follow(self, h: _Heal, flight: asyncio.Future[Reason | None]) -> Any:
        h.waiter = True
        # shield: this call's own deadline must not cancel the leader's future
        verdict = await asyncio.shield(flight)
        if verdict is not None:
            raise _Abort(verdict)
        result = await self._send(h, h.tool.active_fix)
        return result.data if result.cls is ErrorClass.OK else self._safe_api_error(result)

    async def _lead(self, h: _Heal) -> Any:
        if h.outcome.cls is ErrorClass.E3:  # healing an undecodable body is FUTURE
            raise _Abort(Reason.UNSUPPORTED_CLASS)
        fix = self._store.get_active(h.fp)
        if fix:
            h.tier, h.path, h.fix_id = Tier.T0, DecisionPath.cache, fix.fix_id
        else:
            cand = self._store.get_candidate(h.fp)
            if cand:
                fix = cand
                h.tier = Tier.T0
                h.path = DecisionPath.cache
                h.fix_id = cand.fix_id
            else:
                try:
                    if h.outcome.cls is not ErrorClass.E6:
                        await self._diagnose(h)
                    return await self._apply(h, await self._candidate(h))
                except OpError as refused:
                    if not await self._triage(h, refused.reason):
                        raise
                return await self._apply(h, await self._repaired(h))
        return await self._apply(h, fix)

    async def _apply(self, h: _Heal, fix: Fix) -> Any:
        """Gate, optional dry run, verify, commit: the same path for every tier."""
        self._gate(h, fix)
        # Tier-0 fixes still validate against today's spec; the cached wire operation is
        # deliberately not evidence that the upstream still accepts the request.
        current = h.new_op
        if current is None and h.tool.base_op["method"] not in {"MCP", "GRAPHQL", "GRPC"} and self._spec_mode != "off":
            try:
                fresh = await self._spec_source()
            except (httpx.HTTPError, ValueError):
                fresh = None
            if fresh is not None:
                current = fresh.ops.get(h.tool.name)
        h.layers = self._verifier.preflight(
            base_doc=self._validation_doc(h.base), current_spec=(
                {**current, "response_schema": h.tool.base_op.get("response_schema")}
                if current is not None else None
            ),
            fix={"request_ops": fix.request_ops, "response_ops": fix.response_ops},
            original_failure=h.outcome.cls, cfg=self._cfg, tool_cfg=h.tool.config,
            original_status=h.outcome.raw_code,
            no_side_effect=h.outcome.raw_code in {"400", "422"},
        )
        failed = next((row for row in h.layers if row["status"] == "fail"), None)
        if failed:
            if h.tier is Tier.T0:
                self._store.record_result(fix.fix_id, False)
                raise _Abort(Reason.VERIFY_FAILED)
            raise _Abort(_layer_reason(failed["detail"]))
        if h.needs_preverify:
            await self._preverify(h, fix)
        result = await self._verify(h, fix)
        if result.cls is not ErrorClass.OK:
            h.layers = await self._verifier.verify_response(
                results=h.layers, outcome=result, agent_output_schema=h.tool.output_schema,
                base_doc=h.base, tool_cfg=h.tool.config,
            )
            if result.cls is ErrorClass.E1:
                h.transient = True
                self._store.audit(self._event(h, HealOutcome.ABORTED, None))
                return self._safe_api_error(result)
            if h.tier is Tier.T0 and not h.transient:
                self._store.record_result(fix.fix_id, False)
            raise _Abort(self._failure_reason(h, fix, result))
        h.layers = await self._verifier.verify_response(
            results=h.layers, outcome=result, agent_output_schema=h.tool.output_schema,
            base_doc=h.base, tool_cfg=h.tool.config,
            readback=self._readback(h, fix),
            readback_expected=h.base,
            healed_write=bool(h.tool.config.get("write")), deadline=(
                h.deadline.when() if h.deadline else None
            ),
        )
        if any(row["status"] == "fail" for row in h.layers):
            raise _Abort(Reason.VERIFY_FAILED)
        return self._commit(h, fix, result)

    def _validation_doc(self, base: dict) -> dict:
        """Resolve approved config-header refs only in the local L2 validation copy."""
        doc = copy.deepcopy(base)
        approved = {
            name.casefold(): key for name, key in self._header_sources.items()
        }
        for name, value in list(doc.get("header", {}).items()):
            if not isinstance(value, dict) or value.get("ref") != "config":
                continue
            key = value.get("key")
            if approved.get(name.casefold()) == key and key in self._cfg:
                doc["header"][name] = self._cfg[key]
            else:
                doc["header"].pop(name)
        return doc

    def _readback(self, h: _Heal, fix: Fix) -> Callable[[], Awaitable[Any]] | None:
        config = h.tool.config.get("readback")
        if (not config or self._client is None
                or h.tool.base_op["method"] not in {"POST", "GET", "PUT", "PATCH", "DELETE"}):
            return None
        doc = apply_ops(fix.request_ops, h.base, self._cfg)
        key_path = config.get("key_from", [])
        try:
            key = canonical.get(h.base, key_path)
        except (KeyError, TypeError):
            try:
                key = canonical.get(doc, key_path)
            except (KeyError, TypeError):
                return None

        async def read() -> Any:
            key_name = key_path[-1]
            read_key = key
            source = [*key_path]
            moved = False
            for op in fix.request_ops:
                if op.get("op") == "move" and op.get("from") == source:
                    key_name = op["to"][-1] if len(op["to"]) == len(source) else key_name
                    moved = True
            if moved:
                move = next(op for op in fix.request_ops
                    if op.get("op") == "move" and op.get("from") == source)
                read_key = canonical.get(doc, move["to"])
            lookup = {**doc, "body": {key_name: read_key}, "query": {}, "header": {}}
            timeout = min(0.1, max(0.001, (h.deadline.when() if h.deadline else
                asyncio.get_running_loop().time() + 0.1) - asyncio.get_running_loop().time()))
            lookup["route"] = {"method": config["method"], "path": config["route"]}
            response, error = await rest.send(self._client, lookup, timeout)
            return detect.classify(response, error)

        return read

    async def _diagnose(self, h: _Heal) -> None:
        """Fetch and diff the current spec. Leaves `h.ops` None when it is unavailable or off (clue mode)."""
        if self._spec_mode == "off":
            return
        try:
            spec = await self._spec_source()
        except (httpx.HTTPError, ValueError):
            return
        if spec.spec_hash not in self._saved_specs:
            self._store.save_spec(
                spec.spec_hash,
                redact_value(spec.raw, self._secrets),
            )
            self._saved_specs.add(spec.spec_hash)
        h.ops, h.schema_hash = spec.ops, spec.spec_hash
        route = h.base["route"]
        if any(v.path == ["route"] for v in h.outcome.violations) and (
            diagnose.route_exists(h.ops, route["method"], route["path"])
        ):
            raise _Abort(Reason.NOT_DRIFT)
        h.new_op = h.ops.get(h.tool.name) or diagnose.renamed_op(
            h.tool.base_op, h.ops, self._known_tools()
        )
        if h.new_op is None:
            if self._repair is None:
                raise _Abort(Reason.NO_CANDIDATE)
            return  # nothing in the spec matches: the repair agent may still find the operation
        h.entries = diagnose.diff(h.tool.base_op, h.new_op)
        if not h.entries and h.tool.base_op["method"] == "MCP":
            # An MCP error carries no field paths: with the tool's schema unchanged, the
            # rejection is the server's (a business or value error), not drift.
            raise _Abort(Reason.NOT_DRIFT)
        if (
            not h.entries
            and h.outcome.cls is ErrorClass.E2
            and all(v.kind in VALUE_KINDS for v in h.outcome.violations)
        ):  # FR-3.4: the API rejected a value, not the shape
            raise _Abort(Reason.NOT_DRIFT)

    async def _candidate(self, h: _Heal) -> Fix:
        outcome, cfg_keys = h.outcome, set(self._cfg)
        if h.ops is None:
            h.path = DecisionPath.clue
            found, reason = candidates.from_violations(
                outcome.violations,
                h.base,
                self._header_sources,
                cfg_keys,
                outcome.data if outcome.cls is ErrorClass.E5 else None,
                h.tool.output_schema,
            )
        else:
            h.path = DecisionPath.diff
            failing = frozenset(
                tuple(v.path) for v in outcome.violations if v.side is Side.REQ
            )
            if h.entries:
                found, reason = candidates.build(
                    h.entries, h.base, self._header_sources, cfg_keys, failing
                )
            elif h.tool.active_fix is not None:
                # No diff against the base, yet the active fix fails: the API rolled back, so
                # the candidate is "no operations" (FR-3.4). Without a fix nothing explains it.
                found, reason = [{"request_ops": [], "response_ops": []}], None
            else:
                found, reason = [], Reason.NO_CANDIDATE
        if reason is not None:
            raise _Abort(reason)
        index = await self._choose(h, found) if len(found) > 1 else 0
        pick = found[index]
        order = self._schema_order(h)
        pattern = diagnose.abstract_signature(pick.get("request_ops", []), order)
        sig = dict(h.signature)
        sig["abstract"] = pattern
        return Fix(
            h.fp,
            sig,
            h.tool.name,
            outcome.cls,
            pick["request_ops"],
            pick["response_ops"],
            h.tier,
            h.path,
            h.schema_hash,
        )

    def _extend(self, h: _Heal) -> None:
        """Tier 2 gets its own budget (MTTR is reported per tier)."""
        if h.deadline is not None:
            h.deadline.reschedule(
                asyncio.get_running_loop().time() + repair_agent.REPAIR_DEADLINE_S
            )

    async def _triage(self, h: _Heal, reason: Reason) -> bool:
        """FR-17.15: may the repair agent try this refused break? With Jev, Jev decides
        (repair, or send the error to the agent); without Jev only NO_CANDIDATE is tried."""
        if self._repair is None or h.ops is None or h.tier is not Tier.T1:
            return False
        if reason not in REPAIRABLE:
            return False
        write = bool(h.tool.config.get("write"))
        if reason is Reason.VERIFY_FAILED and (h.transient or write):
            return False  # the failed replay may have reached the API
        if reason is Reason.VERIFY_FAILED and h.replay_attempted:
            return False
        if self._jev is None:
            return reason is Reason.NO_CANDIDATE
        self._extend(h)
        state = repair_agent.render(
            h.tool.name, h.tool.base_op, h.ops, h.outcome, h.base, set(self._cfg),
            self._secrets,
        )
        try:
            choice = await self._jev.choose(
                sanitize(f"{state}\nTIER-1 RESULT: refused ({reason.value})", self._secrets),
                TRIAGE_QUESTION,
                list(TRIAGE_OPTIONS),
            )
        except JevUnavailable:
            # An unreachable judge falls back to the no-Jev rule: only a break nothing
            # explains is tried, and the fix still passes the gate and live verification.
            return reason is Reason.NO_CANDIDATE
        h.jev_tokens += choice.tokens
        h.path = DecisionPath.jev
        return choice.index == 0 and safety.jev_ok(choice.confidence, write)

    async def _repaired(self, h: _Heal) -> Fix:
        """Tier 2 (S3): the repair agent's proposal, checked here, then gated and verified
        like any fix. Only a refusal `_triage` lets through gets here; a missing value
        (NO_SAFE_VALUE) never does, so the model is never asked to supply one."""
        self._extend(h)
        h.tier, h.path = Tier.T2, DecisionPath.repair
        prompt = repair_agent.render(
            h.tool.name, h.tool.base_op, h.ops, h.outcome, h.base, set(self._cfg),
            self._secrets,
        )
        try:
            proposal, h.llm_tokens = await self._repair.propose(prompt)
        except repair_agent.RepairUnavailable:
            raise _Abort(Reason.NO_CANDIDATE) from None
        if proposal.get("operation") is None:
            raise _Abort(Reason.NO_CANDIDATE)
        try:
            h.new_op, req, resp = repair_agent.check(proposal, h.tool.base_op, h.ops)
        except ValueError:
            raise _Abort(Reason.UNSAFE_PATCH) from None
        h.entries = diagnose.diff(h.tool.base_op, h.new_op)
        h.needs_preverify = bool(
            h.tool.config.get("write")
        )  # FR-8.6, as for a Jev pick
        sig = dict(h.signature)
        sig["abstract"] = diagnose.abstract_signature(req, self._schema_order(h))
        return Fix(
            h.fp,
            sig,
            h.tool.name,
            h.outcome.cls,
            req,
            resp,
            Tier.T2,
            DecisionPath.repair,
            h.schema_hash,
        )

    async def _choose(self, h: _Heal, found: list[dict]) -> int:
        """FR-7.6, then FR-8: the tie-breaker's unique winner, else Jev's pick, else an abort."""
        write = bool(h.tool.config.get("write"))
        winner = candidates.tiebreak(found, self._schema_order(h), write=write)
        if winner is not None:
            h.path = DecisionPath.tiebreak
            return winner
        order = self._schema_order(h)
        for idx, cand in enumerate(found):
            pat = diagnose.abstract_signature(cand.get("request_ops", []), order)
            if self._store.is_rule(pat):
                h.path = DecisionPath.tiebreak
                return idx
        h.path = DecisionPath.jev
        try:
            if self._jev is None:
                raise JevUnavailable
            choice = await self._jev.choose(
                sanitize(render_state(h.entries, h.base), self._secrets),
                QUESTION,
                [sanitize(render_option(f), self._secrets) for f in found],
            )
        except JevUnavailable:
            h.path = DecisionPath.jev_unavailable
            raise _Abort(Reason.LOW_CONFIDENCE) from None
        h.jev_tokens = choice.tokens
        if not safety.jev_ok(choice.confidence, write):
            raise _Abort(Reason.LOW_CONFIDENCE)
        h.needs_preverify = write  # FR-8.6: a write waits for the dry run to confirm
        return choice.index

    @staticmethod
    def _schema_order(h: _Heal) -> list[dict]:
        """diagnose.diff sorts by path; the tie-breaker's order evidence needs declaration order."""
        if h.new_op is None:
            return h.entries
        rank = {
            ("removed", p): i
            for i, p in enumerate(diagnose.flatten_request(h.tool.base_op))
        } | {("added", p): i for i, p in enumerate(diagnose.flatten_request(h.new_op))}
        return sorted(
            h.entries, key=lambda e: rank.get((e["change"], tuple(e["path"])), -1)
        )

    async def _preverify(self, h: _Heal, fix: Fix) -> None:
        """FR-8.6: send the chosen request once to the tool's side-effect-free route. Only a
        clean result (detection, output schema, postchecks) confirms the Jev pick."""
        route = h.tool.config.get("preverify")
        if route is None:
            raise _Abort(Reason.LOW_CONFIDENCE)
        result = await self._send(h, fix, route)
        h.transient = result.cls is ErrorClass.E1
        if result.cls is not ErrorClass.OK:
            raise _Abort(Reason.LOW_CONFIDENCE)

    def _gate(self, h: _Heal, fix: Fix) -> None:
        spec_paths = spec_routes = None
        if h.new_op is not None:
            # Response ops write into the agent's (base) response shape, so its leaves count too.
            spec_paths = (
                set(diagnose.flatten_request(h.new_op))
                | set(diagnose.flatten_response(h.new_op))
                | set(diagnose.flatten_response(h.tool.base_op))
            )
            spec_routes = {(o["method"], o["path"]) for o in h.ops.values()}
        reason = safety.check(
            {"request_ops": fix.request_ops, "response_ops": fix.response_ops},
            base_doc=h.base,
            cfg=self._cfg,
            cls=h.outcome.cls,
            tool_cfg=h.tool.config,
            # ponytail: tier 0 has no diff, so its op cap is counted from the violations alone.
            n_evidence=max(len(h.entries), len(h.outcome.violations)),
            spec_paths=spec_paths,
            spec_routes=spec_routes,
        )
        if reason is not None:
            raise _Abort(reason)

    def _local(self, h: _Heal, fix: Fix) -> bool:
        """A response-only fix on E5 reshapes the body already received; nothing is re-sent."""
        return not safety.replays(h.outcome.cls, fix.request_ops, fix.response_ops)

    async def _verify(self, h: _Heal, fix: Fix) -> Outcome:
        if not self._local(h, fix):
            h.replay_attempted = True
            return await self._send(h, fix)
        data = apply_ops(fix.response_ops, h.outcome.data, self._cfg)
        return contract.check(
            replace(h.outcome, cls=ErrorClass.OK, violations=[], data=data),
            output_schema=h.tool.output_schema,
            postchecks=h.tool.config["postchecks"],
            base_doc=h.base,
        )

    async def _send(
        self, h: _Heal, fix: Fix | None, route: dict | None = None
    ) -> Outcome:
        when = h.deadline.when() if h.deadline else None
        if when is None:
            remaining = HEAL_DEADLINE_S - (self._clock() - h.t0)
        else:  # the live deadline: tier 2 may have extended it
            remaining = when - asyncio.get_running_loop().time()
        return await self._attempt(
            h.tool, h.base, fix, min(REPLAY_TIMEOUT_MAX_S, remaining), route
        )

    def _failure_reason(self, h: _Heal, fix: Fix, result: Outcome) -> Reason:
        wrote = result.cls is ErrorClass.E6 and h.tool.config.get("write")
        if wrote and not self._local(h, fix):
            return Reason.POSTCHECK_FAILED_AFTER_WRITE
        return Reason.VERIFY_FAILED

    def _commit(self, h: _Heal, fix: Fix, result: Outcome) -> Any:
        try:
            if fix.status is FixStatus.candidate:
                self._store.promote(fix.fix_id)
                self._store.record_result(fix.fix_id, True)
                fix.status = FixStatus.active
            elif (
                h.tier is Tier.T0
            ):  # a replay of one fix is not new evidence for a rule
                self._store.record_result(fix.fix_id, True)
            else:
                h.fix_id = self._store.save_fix(fix)
            if h.tier is not Tier.T0 and (pat := fix.signature.get("abstract")):
                self._store.record_rule_win(pat)
            self._store.audit(self._event(h, HealOutcome.RECOVERED, None))
        except sqlite3.Error:  # a fix that cannot be logged is not applied
            raise _Abort(Reason.VERIFY_FAILED) from None
        self._first_seen.pop(h.fp, None)
        h.tool.active_fix = fix
        h.tool.version += 1
        if (
            h.new_op is not None
        ):  # tier 0 skips the spec fetch, so there is nothing newer
            h.tool.wire_op = h.new_op
        self._propagate_siblings(h, fix)
        return result.data

    def _propagate_siblings(self, h: _Heal, fix: Fix) -> None:
        """FR-17.1 (S1): Propagate candidate fixes to sibling tools sharing the removed field/type."""
        if self._tools is None or not fix.request_ops:
            return
        base_leaves = diagnose.flatten_request(h.tool.base_op)
        affected_leaves: list[tuple[dict, dict]] = []
        for op in fix.request_ops:
            if op.get("op") == "move":
                src = tuple(op["from"])
                if src in base_leaves:
                    affected_leaves.append((base_leaves[src], op))
            elif op.get("op") == "cast":
                path = tuple(op["path"])
                if path in base_leaves:
                    affected_leaves.append((base_leaves[path], op))
        if not affected_leaves:
            return

        for tool in self._tools():
            if tool.name == h.tool.name:
                continue
            sibling_leaves = diagnose.flatten_request(tool.base_op)
            sibling_ops = []
            for leaf, op in affected_leaves:
                src_path = tuple(op["from"] if op["op"] == "move" else op["path"])
                if (
                    src_path in sibling_leaves
                    and sibling_leaves[src_path]["type"] == leaf["type"]
                ):
                    sibling_ops.append(op)

            if sibling_ops:
                sibling_sig = {k: v for k, v in h.signature.items() if k != "abstract"}
                sibling_sig["tool"] = tool.name
                sibling_fp = canonical.sha256(sibling_sig)[:16]
                sibling_sig["abstract"] = fix.signature.get("abstract", "")
                if not self._store.get_active(
                    sibling_fp
                ) and not self._store.get_candidate(sibling_fp):
                    cand = Fix(
                        fingerprint=sibling_fp,
                        signature=sibling_sig,
                        tool=tool.name,
                        cls=fix.cls,
                        request_ops=sibling_ops,
                        response_ops=[],
                        tier=Tier.T0,
                        source=DecisionPath.diff,
                        schema_hash=fix.schema_hash,
                        status=FixStatus.candidate,
                    )
                    self._store.save_fix(cand)

    def _known_tools(self) -> set[str]:
        return {t.name for t in self._tools()} if self._tools else set()

    async def precompute(self, old: LoadedSpec, new: LoadedSpec) -> int:
        """FR-17.11 (X4): Precompute candidate fixes from spec diffs before any failure occurs.
        Stores fixes with status candidate; sends 0 live requests. Returns count of fixes stored."""
        if new.spec_hash not in self._saved_specs:
            self._store.save_spec(
                new.spec_hash,
                redact_value(new.raw, self._secrets),
            )
            self._saved_specs.add(new.spec_hash)

        tools_by_name = {t.name: t for t in self._tools()} if self._tools else {}
        count = 0
        cfg_keys = set(self._cfg)

        for tool_name, old_op in old.ops.items():
            new_op = new.ops.get(tool_name) or diagnose.renamed_op(
                old_op, new.ops, old.ops
            )
            if new_op is None:
                continue
            entries = diagnose.diff(old_op, new_op)
            if not entries:
                continue

            tool = tools_by_name.get(tool_name)
            if tool is not None:
                dummy_args = {
                    p[-1]: 1 if leaf.get("type") in ("int", "integer") else "sample"
                    for p, leaf in diagnose.flatten_request(tool.base_op).items()
                }
                base = {
                    "route": {
                        "method": tool.base_op["method"],
                        "path": tool.base_op["path"],
                    },
                    "body": {
                        k: v
                        for k, v in dummy_args.items()
                        if ("body", k) in diagnose.flatten_request(tool.base_op)
                    },
                    "query": {
                        k: v
                        for k, v in dummy_args.items()
                        if ("query", k) in diagnose.flatten_request(tool.base_op)
                    },
                    "route_params": {
                        k: v
                        for k, v in dummy_args.items()
                        if ("route_params", k) in diagnose.flatten_request(tool.base_op)
                    },
                    "header": {},
                }
            else:
                base = {
                    "route": {"method": old_op["method"], "path": old_op["path"]},
                    "body": {
                        k: 1 if v.get("type") == "integer" else "sample"
                        for k, v in (old_op.get("body_schema") or {})
                        .get("properties", {})
                        .items()
                    },
                    "query": {
                        p["name"]: 1
                        if p.get("schema", {}).get("type") == "integer"
                        else "sample"
                        for p in old_op.get("params", [])
                        if p.get("in") == "query"
                    },
                    "route_params": {
                        p["name"]: "sample"
                        for p in old_op.get("params", [])
                        if p.get("in") == "path"
                    },
                    "header": {},
                }

            failing = frozenset(
                tuple(e["path"])
                for e in entries
                if e["side"] == Side.REQ and e["change"] in ("added", "type_changed")
            )
            found, reason = candidates.build(
                entries, base, self._header_sources, cfg_keys, failing
            )
            if not found or reason is not None:
                continue

            write = bool(tool.config.get("write")) if tool else False
            rank = {
                ("removed", p): i
                for i, p in enumerate(diagnose.flatten_request(old_op))
            } | {
                ("added", p): i for i, p in enumerate(diagnose.flatten_request(new_op))
            }
            order = sorted(
                entries, key=lambda e: rank.get((e["change"], tuple(e["path"])), -1)
            )
            winner = (
                candidates.tiebreak(found, order, write=write) if len(found) > 1 else 0
            )
            if winner is None:
                continue
            pick = found[winner]

            req_entries = [e for e in entries if e["side"] == Side.REQ]
            added_req = [
                e for e in req_entries if e["change"] == "added" and e.get("required")
            ]
            type_req = [e for e in req_entries if e["change"] == "type_changed"]

            diff_sig = None
            if any(
                e["path"][0] == "header" and e["path"][1] == "authorization"
                for e in added_req
            ):
                cls = ErrorClass.E4
                raw_code = "401"
                v_list = [Violation(Side.REQ, ["header", "authorization"], "missing")]
            elif added_req:
                cls = ErrorClass.E2
                raw_code = "422"
                v_list = [Violation(Side.REQ, e["path"], "missing") for e in added_req]
            elif type_req:
                cls = ErrorClass.E2
                raw_code = "422"
                v_list = [
                    Violation(Side.REQ, e["path"], f"{e['type']}_type")
                    for e in type_req
                ]
            else:
                cls = ErrorClass.E6
                raw_code = "200"
                diff_sig = diagnose.diff_signature(entries)
                v_list = []

            protocol = "rest"
            if (
                old_op["method"] == "MCP"
            ):  # the failure shape adapters/mcp_upstream.send returns
                moved = any(e["change"] == "route_changed" for e in entries)
                protocol, cls, diff_sig = "mcp", ErrorClass.E2, None
                raw_code = "-32601" if moved else "isError"
                v_list = [
                    Violation(Side.REQ, ["route"], "route")
                    if moved
                    else Violation(Side.REQ, [], "rejected")
                ]
            predicted = Outcome(
                cls=cls, protocol=protocol, raw_code=raw_code, violations=v_list
            )
            fp, sig = fingerprint.fingerprint(tool_name, predicted, diff_sig)
            sig["abstract"] = diagnose.abstract_signature(
                pick.get("request_ops", []), order
            )

            if not self._store.get_active(fp) and not self._store.get_candidate(fp):
                cand_fix = Fix(
                    fingerprint=fp,
                    signature=sig,
                    tool=tool_name,
                    cls=cls,
                    request_ops=pick["request_ops"],
                    response_ops=pick["response_ops"],
                    tier=Tier.T0,
                    source=DecisionPath.diff,
                    schema_hash=new.spec_hash,
                    status=FixStatus.candidate,
                )
                self._store.save_fix(cand_fix)
                count += 1

        return count

    def _abort(self, h: _Heal, reason: Reason) -> Any:
        if not h.waiter:
            # A missing, slow or broken Jev says nothing about the break (FR-11.3).
            transient = h.transient or h.path is DecisionPath.jev_unavailable
            if reason in NEGATIVE and not transient:
                self._store.add_negative(h.fp)
            outcome = AUDIT_OUTCOME.get(reason, HealOutcome.ABORTED)
            self._store.audit(self._event(h, outcome, reason))
        if reason is Reason.NOT_DRIFT:
            return self._safe_api_error(replace(h.outcome, cls=ErrorClass.BUSINESS))
        return HealError(h.tool.name, h.outcome.cls, h.fp, reason).to_dict()

    def _safe_api_error(self, outcome: Outcome) -> dict:
        error = api_error(outcome)
        error["detail"] = redact_value(error["detail"], self._secrets)
        return error

    def sanitize_spec(self, raw: dict) -> dict:
        """Redact a persisted spec copy without changing the live loaded schema."""
        return redact_value(raw, self._secrets)

    def _event(
        self, h: _Heal, outcome: HealOutcome, reason: Reason | None
    ) -> AuditEvent:
        now = self._clock()
        first = self._first_seen.setdefault(h.fp, h.detected)
        violations = [[v.side, v.path, v.kind] for v in h.outcome.violations]
        # Only an error response carries an error body; an E5/E6 body is an ordinary reply.
        err = h.outcome.cls in (ErrorClass.E2, ErrorClass.E4)
        blob = {
            "code": h.outcome.raw_code,
            "body": h.outcome.data if err else None,
            "violations": violations,
        }
        return AuditEvent(
            ts_ms=time.time_ns() // 1_000_000,
            tool=h.tool.name,
            fingerprint=h.fp,
            cls=h.outcome.cls,
            raw_code=h.outcome.raw_code,
            tier=h.tier,
            path=h.path,
            fix_id=h.fix_id,
            outcome=outcome,
            reason=reason,
            mttr_ms=int((now - first) * 1000),
            heal_ms=int((now - h.detected) * 1000),
            jev_tokens=h.jev_tokens,
            llm_tokens=h.llm_tokens,
            raw_error=canonical.dumps(redact_value(blob, self._secrets)),
            layers=h.layers,
        )
