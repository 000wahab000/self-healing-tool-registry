"""Deterministic preflight and post-response verification."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from jsonschema import Draft202012Validator

from healer import contract, safety
from healer.canonical import get
from healer.models import ErrorClass, OperationSpec, Outcome
from healer.ops import apply_ops

Readback = Callable[[], Awaitable[Any]]


def _strict(schema: dict) -> dict:
    result = dict(schema)
    if result.get("type") == "object" or "properties" in result:
        result["additionalProperties"] = False
        result["properties"] = {k: _strict(v) for k, v in result.get("properties", {}).items()}
    for key in ("items", "not", "if", "then", "else"):
        if isinstance(result.get(key), dict):
            result[key] = _strict(result[key])
    for key in ("oneOf", "anyOf", "allOf", "prefixItems"):
        if isinstance(result.get(key), list):
            result[key] = [_strict(item) for item in result[key]]
    return result


def _row(layer: int, name: str, status: str, detail: str = "ok") -> dict[str, str]:
    return {"layer": f"L{layer}", "name": name, "status": status, "detail": detail}


def _skip_from(start: int) -> list[dict[str, str]]:
    names = ["safety", "request_schema", "response_schema", "postchecks", "readback", "invariants", "replay_safety"]
    return [_row(i, names[i - 1], "skip", "not_reached") for i in range(start, 8)]


def _spec_constraints(spec: OperationSpec | None) -> tuple[set[tuple] | None, set[tuple[str, str]] | None]:
    if spec is None:
        return None, None
    paths: set[tuple] = set()
    # enum values are collected separately from legal schema paths.

    def collect(schema: dict, at: tuple) -> None:
        for key, child in schema.get("properties", {}).items():
            path = at + (key,)
            paths.add(path)
            if isinstance(child, dict):
                collect(child, path)

    collect(spec.get("body_schema") or {}, ("body",))
    collect(spec.get("response_schema") or {}, ())
    for param in spec.get("params", []):
        loc = param.get("in", "query")
        paths.add(
            (
                "route_params" if loc == "path" else loc,
                param["name"].casefold() if loc == "header" else param["name"],
            )
        )
    if "bearer" in spec.get("security", []):
        paths.add(("header", "authorization"))
    return paths, {(spec["method"], spec["path"])}


class Verifier:
    """Use ``preflight`` before sending, then ``verify_response`` after replay."""

    def __init__(self, *, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self.sleep = sleep

    def preflight(
        self, *, base_doc: dict, current_spec: OperationSpec | None, fix: dict,
        original_failure: ErrorClass, cfg: Mapping[str, str], tool_cfg: dict,
        original_status: str | None = None, no_side_effect: bool = False,
    ) -> list[dict[str, str]]:
        paths, routes = _spec_constraints(current_spec)
        reason = safety.check(
            fix, base_doc=base_doc, cfg=cfg,
            cls=ErrorClass.OK if original_failure is ErrorClass.E5 else original_failure,
            # Replay authorization is recorded independently as L7 below.
            tool_cfg={**tool_cfg, "idempotent": True},
            n_evidence=max(1, len(fix.get("request_ops", [])) + len(fix.get("response_ops", []))),
        spec_paths=paths, spec_routes=routes,
        )
        first = _row(1, "safety", "fail" if reason else "pass", reason.value if reason else "ok")
        if reason:
            return [first, *_skip_from(2)]
        if current_spec is None:
            second = _row(2, "request_schema", "skip", "spec_unavailable")
        elif current_spec["method"] in {"MCP", "GRAPHQL", "GRPC"}:
            second = _row(2, "request_schema", "skip", "protocol_schema")
        else:
            patched = apply_ops(fix.get("request_ops", []), base_doc, cfg)
            second = _row(2, "request_schema", "fail" if _invalid_request(patched, current_spec) else "pass",
                          "schema_invalid" if _invalid_request(patched, current_spec) else "ok")
        if second["status"] == "fail":
            return [first, second, *_skip_from(3)]
        keyed = any("idempotency-key" in str(k).casefold() and v for k, v in base_doc.get("header", {}).items())
        rejected = original_failure is ErrorClass.E2 and original_status in {"400", "422"} and no_side_effect
        unsafe = bool(
            tool_cfg.get("write") and not tool_cfg.get("idempotent")
            and not keyed and not rejected
        )
        seventh = _row(7, "replay_safety", "fail" if unsafe else "pass", "unsafe_replay" if unsafe else "ok")
        return [first, second, _row(3, "response_schema", "skip", "not_reached"),
                _row(4, "postchecks", "skip", "not_reached"), _row(5, "readback", "skip", "not_reached"),
                _row(6, "invariants", "skip", "not_reached"), seventh]

    async def verify_response(
        self, *, results: list[dict[str, str]], outcome: Outcome,
        agent_output_schema: dict | None, base_doc: dict, tool_cfg: dict,
        healed_write: bool = False, readback: Readback | None = None,
        readback_expected: Any = None,
        deadline: float | None = None,
    ) -> list[dict[str, str]]:
        if any(row["status"] == "fail" for row in results[:2]) or results[6]["status"] == "fail":
            return results
        if outcome.cls is not ErrorClass.OK:
            results[2] = _row(3, "response_schema", "fail", "replay_failed")
            results[3:] = _skip_from(4)
            return results
        checked = contract.check(outcome, output_schema=agent_output_schema,
                                 postchecks=tool_cfg.get("postchecks", []), base_doc=base_doc)
        results[2] = _row(3, "response_schema", "fail" if checked.cls is ErrorClass.E5 else "pass",
                          "schema_invalid" if checked.cls is ErrorClass.E5 else "ok")
        results[3] = _row(4, "postchecks", "fail" if checked.cls is ErrorClass.E6 else "pass",
                          "postcheck_failed" if checked.cls is ErrorClass.E6 else "ok")
        if results[2]["status"] == "fail":
            results[3:] = _skip_from(4)
            return results
        if results[3]["status"] == "fail":
            results[4:] = _skip_from(5)
            return results
        if not (healed_write and readback is not None):
            results[4] = _row(5, "readback", "skip", "not_healed_write")
        else:
            good = False
            detail = "readback_mismatch"
            for attempt in range(2):
                if deadline is not None and time.monotonic() >= deadline:
                    detail = "deadline"
                    break
                try:
                    observed = await readback()
                    if isinstance(observed, Outcome):
                        if observed.cls is not ErrorClass.OK:
                            detail = "readback_unavailable"
                            good = False
                        else:
                            observed = observed.data
                    if detail != "readback_unavailable":
                        good = _readback_matches(
                            observed, outcome.data if readback_expected is None else readback_expected,
                            tool_cfg.get("readback", []),
                        )
                        detail = "ok" if good else "readback_mismatch"
                except (TimeoutError, OSError):
                    detail = "readback_unavailable"
                if good or attempt:
                    break
                if deadline is not None and time.monotonic() + 0.1 >= deadline:
                    detail = "deadline"
                    break
                await self.sleep(0.1)
            results[4] = _row(5, "readback", "pass" if good else "fail", detail)
        valid = _invariants_pass(outcome.data, base_doc, tool_cfg.get("invariants", []))
        results[5] = _row(6, "invariants", "pass" if valid else "fail", "ok" if valid else "invariant_failed")
        results[6] = _row(7, "replay_safety", "pass", "preflight_passed")
        return results


def _invalid_request(doc: dict, spec: OperationSpec) -> bool:
    body_schema = spec.get("body_schema")
    if body_schema and not Draft202012Validator(_strict(body_schema)).is_valid(doc.get("body", {})):
        return True
    params = spec.get("params", [])
    for param in params:
        loc, name = param.get("in", "query"), param["name"]
        doc_loc = "route_params" if loc == "path" else loc
        values = doc.get(doc_loc, {})
        if loc == "header":
            values = {str(key).casefold(): value for key, value in values.items()}
            name = name.casefold()
        if param.get("required") and name not in values:
            return True
        if name in values and not Draft202012Validator(_strict(param["schema"])).is_valid(values[name]):
            return True
    query_names = {param["name"] for param in params if param.get("in", "query") == "query"}
    path_names = {param["name"] for param in params if param.get("in") == "path"}
    if "bearer" in spec.get("security", []):
        headers = {str(key).casefold(): value for key, value in doc.get("header", {}).items()}
        if not isinstance(headers.get("authorization"), str) or not headers["authorization"]:
            return True
    return bool(
        set(doc.get("query", {})) - query_names
        or set(doc.get("route_params", {})) - path_names
    )


def _readback_matches(observed: Any, expected: Any, checks: list[dict]) -> bool:
    if isinstance(checks, dict):
        paths = checks.get("compare", [])
        try:
            return all(
                get(observed, path if isinstance(path, list) else [path])
                == get(expected, ["body", *(path if isinstance(path, list) else [path])])
                for path in paths
            )
        except (KeyError, TypeError):
            return False
    if not checks:
        return observed == expected
    try:
        return all(get(observed, check["response"]) == get(expected, check["expected"]) for check in checks)
    except (KeyError, TypeError):
        return False


def _invariants_pass(data: Any, base_doc: dict, invariants: list[dict]) -> bool:
    for check in invariants:
        try:
            value = get(data, check["response"])
            kind = check["type"]
            if kind == "id_equals_request":
                good = str(value).strip().casefold() == str(get(base_doc, check["request"])).strip().casefold()
            elif kind == "non_empty":
                good = bool(value)
            elif kind == "list_not_shrunk":
                good = isinstance(value, list) and len(value) >= len(get(base_doc, check["request"]))
            elif kind == "type_is":
                types = {"string": str, "integer": int, "number": (int, float), "object": dict, "array": list, "boolean": bool}
                good = type(value) in types.get(check["value"], ())
            elif kind == "range":
                good = isinstance(value, (int, float)) and check["min"] <= value <= check["max"]
            else:
                good = False
            if not good:
                return False
        except (KeyError, TypeError):
            return False
    return True


async def verify(*, base_doc: dict, current_spec: OperationSpec | None, fix: dict,
                 cfg: Mapping[str, str], tool_cfg: dict, response: Outcome,
                 readback: Readback | None = None,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 deadline: float | None = None) -> list[dict[str, str]]:
    """Compatibility wrapper; integrations should use preflight/verify_response explicitly."""
    verifier = Verifier(sleep=sleep)
    results = verifier.preflight(base_doc=base_doc, current_spec=current_spec, fix=fix,
                                 original_failure=response.cls, cfg=cfg, tool_cfg=tool_cfg)
    return await verifier.verify_response(results=results, outcome=response,
        agent_output_schema=(current_spec or {}).get("response_schema"), base_doc=base_doc,
        tool_cfg=tool_cfg, healed_write=bool(tool_cfg.get("write")), readback=readback, deadline=deadline)
