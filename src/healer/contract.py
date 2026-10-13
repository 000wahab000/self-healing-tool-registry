"""Output-schema validation (E5) and declarative postchecks (E6) on an OK outcome."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from jsonschema import Draft202012Validator

from healer.canonical import get
from healer.models import ErrorClass, Outcome, PostcheckType, Side, Violation


def _schema_violations(data: Any, schema: dict) -> list[Violation]:
    # keyed to dedupe: jsonschema yields one `required` error per property, each expanded below
    found: dict[tuple, Violation] = {}
    for err in Draft202012Validator(schema).iter_errors(data):
        base = list(err.absolute_path)
        if err.validator == "required":
            paths = [base + [p] for p in err.validator_value if p not in err.instance]
            kind = "missing"
        else:
            paths, kind = [base], str(err.validator)
        for path in paths:
            found.setdefault((tuple(path), kind), Violation(Side.RESP, path, kind))
    return list(found.values())


def _passes(pc: dict, data: Any, base_doc: dict) -> bool:
    try:
        got = get(data, pc["response"])
        if PostcheckType(pc["type"]) is PostcheckType.echo:
            return str(got) == str(get(base_doc, pc["request"]))
        return bool(got)
    except KeyError:  # a missing path is a failed check
        return False


def check(
    outcome: Outcome,
    *,
    output_schema: dict | None,
    postchecks: list[dict],
    base_doc: dict,
) -> Outcome:
    if outcome.cls is not ErrorClass.OK:
        return outcome
    if output_schema:
        violations = _schema_violations(outcome.data, output_schema)
        if violations:
            return replace(outcome, cls=ErrorClass.E5, violations=violations)
    failed = [
        Violation(Side.REQ, list(pc.get("request") or []), "postcheck")
        for pc in postchecks
        if not _passes(pc, outcome.data, base_doc)
    ]
    if failed:
        return replace(outcome, cls=ErrorClass.E6, violations=failed)
    return outcome
