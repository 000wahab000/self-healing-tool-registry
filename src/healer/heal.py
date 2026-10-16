"""Heal Controller (FR-10, FR-11): at most one heal attempt per failed call, one audit event per attempt."""

from __future__ import annotations

import asyncio
import sqlite3
import time
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

import httpx

from healer import candidates, canonical, contract, diagnose, fingerprint, safety
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
    Outcome,
    Reason,
    Side,
    SpecSource,
    Tier,
)
from healer.ops import OpError, apply_ops
from healer.settings import HEAL_DEADLINE_S, REPLAY_TIMEOUT_MAX_S, SPEC_MODE
from healer.store import FixStore, sanitize

if TYPE_CHECKING:
    from healer.registry import ToolDefinition

QUESTION = (
    "Which candidate fix correctly adapts the agent's request to the changed API?"
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
    waiter: bool = False  # single-flight follower: writes no audit event
    ops: dict | None = None  # operations of the current spec; None in clue mode
    new_op: dict | None = None
    entries: list[dict] = field(default_factory=list)
    schema_hash: str = ""
    transient: bool = False  # the replay hit E1
    needs_preverify: bool = False  # a Jev pick on a write tool (FR-8.6)


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
    ) -> None:
        self._store, self._jev, self._spec_source = store, jev, spec_source
        self._spec_mode = spec_mode
        self._cfg, self._header_sources = cfg, header_sources
        self._attempt, self._clock = attempt, clock
        self._tools = tools
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
        h.fp, h.signature = fingerprint.fingerprint(tool.name, outcome)
        try:
            async with asyncio.timeout(HEAL_DEADLINE_S - (self._clock() - t0)):
                return await self._run(h)
        except TimeoutError:
            reason = Reason.DEADLINE
        except OpError as e:
            reason = e.reason
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
        return result.data if result.cls is ErrorClass.OK else api_error(result)

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
                if h.outcome.cls is not ErrorClass.E6:
                    await self._diagnose(h)
                fix = await self._candidate(h)
        self._gate(h, fix)
        if h.needs_preverify:
            await self._preverify(h, fix)
        result = await self._verify(h, fix)
        if result.cls is not ErrorClass.OK:
            # A transient replay failure says nothing about the fix: no loss, no negative cache.
            h.transient = result.cls is ErrorClass.E1
            if h.tier is Tier.T0 and not h.transient:
                self._store.record_result(fix.fix_id, False)
            raise _Abort(self._failure_reason(h, fix, result))
        return self._commit(h, fix, result)

    async def _diagnose(self, h: _Heal) -> None:
        """Fetch and diff the current spec. Leaves `h.ops` None when it is unavailable or off (clue mode)."""
        if self._spec_mode == "off":
            return
        try:
            spec = await self._spec_source()
        except (httpx.HTTPError, ValueError):
            return
        if spec.spec_hash not in self._saved_specs:
            self._store.save_spec(spec.spec_hash, spec.raw)
            self._saved_specs.add(spec.spec_hash)
        h.ops, h.schema_hash = spec.ops, spec.spec_hash
        route = h.base["route"]
        if any(v.path == ["route"] for v in h.outcome.violations) and (
            diagnose.route_exists(h.ops, route["method"], route["path"])
        ):
            raise _Abort(Reason.NOT_DRIFT)
        h.new_op = h.ops.get(h.tool.name)
        if h.new_op is None:
            raise _Abort(Reason.NO_CANDIDATE)
        h.entries = diagnose.diff(h.tool.base_op, h.new_op)
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
                render_state(h.entries, h.base),
                QUESTION,
                [render_option(f) for f in found],
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
        remaining = HEAL_DEADLINE_S - (self._clock() - h.t0)
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
            elif h.tier is Tier.T0:
                self._store.record_result(fix.fix_id, True)
            else:
                h.fix_id = self._store.save_fix(fix)
                pat = fix.signature.get("abstract")
                if pat:
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
                if not self._store.get_active(sibling_fp) and not self._store.get_candidate(sibling_fp):
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

    def _abort(self, h: _Heal, reason: Reason) -> Any:
        if not h.waiter:
            # A missing, slow or broken Jev says nothing about the break (FR-11.3).
            transient = h.transient or h.path is DecisionPath.jev_unavailable
            if reason in NEGATIVE and not transient:
                self._store.add_negative(h.fp)
            outcome = AUDIT_OUTCOME.get(reason, HealOutcome.ABORTED)
            self._store.audit(self._event(h, outcome, reason))
        if reason is Reason.NOT_DRIFT:
            return api_error(replace(h.outcome, cls=ErrorClass.BUSINESS))
        return HealError(h.tool.name, h.outcome.cls, h.fp, reason).to_dict()

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
            raw_error=sanitize(canonical.dumps(blob), self._cfg.values()),
        )
