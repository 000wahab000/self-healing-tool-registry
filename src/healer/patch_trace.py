"""Request-local record of safe fix operations actually applied during an MCP call."""

from __future__ import annotations

import copy
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field

from healer.models import Fix, FixStatus


@dataclass
class _AppliedFix:
    fix: Fix
    reused: bool
    request_ops: list[dict] = field(default_factory=list)
    response_ops: list[dict] = field(default_factory=list)


@dataclass
class PatchCallTrace:
    _uses: list[_AppliedFix] = field(default_factory=list)

    def _use(self, fix: Fix) -> _AppliedFix:
        for applied in self._uses:
            if applied.fix is fix:
                return applied
        # This includes a stored active fix recovered in this call, not only one already attached.
        applied = _AppliedFix(
            fix=fix,
            reused=fix.fix_id is not None and fix.status is FixStatus.active,
        )
        self._uses.append(applied)
        return applied

    def request(self, fix: Fix) -> None:
        if fix.request_ops:
            applied = self._use(fix)
            applied.request_ops = copy.deepcopy(fix.request_ops)

    def response(self, fix: Fix) -> None:
        if fix.response_ops:
            applied = self._use(fix)
            applied.response_ops = copy.deepcopy(fix.response_ops)

    def as_list(self) -> list[dict]:
        return [
            {
                "fix_id": applied.fix.fix_id,
                "reused": applied.reused,
                "request_ops": applied.request_ops,
                "response_ops": applied.response_ops,
            }
            for applied in self._uses
            if applied.request_ops or applied.response_ops
        ]


_CURRENT: ContextVar[PatchCallTrace | None] = ContextVar("patch_call_trace", default=None)


@contextmanager
def collect_patch_call() -> Iterator[PatchCallTrace]:
    trace = PatchCallTrace()
    token: Token[PatchCallTrace | None] = _CURRENT.set(trace)
    try:
        yield trace
    finally:
        _CURRENT.reset(token)


def request_applied(fix: Fix | None) -> None:
    trace = _CURRENT.get()
    if trace is not None and fix is not None:
        trace.request(fix)


def response_applied(fix: Fix | None) -> None:
    trace = _CURRENT.get()
    if trace is not None and fix is not None:
        trace.response(fix)
