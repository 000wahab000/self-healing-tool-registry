"""GraphQL HTTP transport and machine-readable error normalization."""

from __future__ import annotations

import json

import httpx

from healer.models import ErrorClass, Outcome, Side, Violation


def _selection(schema: dict) -> str:
    if schema.get("type") != "object":
        return ""
    return " { " + " ".join(f"{name}{_selection(value)}" for name, value in schema.get("properties", {}).items()) + " }"


def _literal(value: object) -> str:
    return json.dumps(value, separators=(",", ":"))


def _arg_violations(variables: dict, schema: dict) -> list[Violation]:
    props = schema.get("body_schema", {}).get("properties", {})
    errors = [Violation(Side.REQ, ["body", key], "unknown") for key in variables.keys() - props.keys()]
    errors.extend(
        Violation(Side.REQ, ["body", key], "missing")
        for key in schema.get("body_schema", {}).get("required", [])
        if key not in variables
    )
    for key, value in variables.items():
        want = props.get(key, {}).get("type")
        actual = "boolean" if isinstance(value, bool) else "integer" if isinstance(value, int) else "number" if isinstance(value, float) else "string" if isinstance(value, str) else None
        if want and actual and want != actual and not (want == "number" and actual == "integer"):
            errors.append(Violation(Side.REQ, ["body", key], "type"))
    return errors


def _query(operation: str, variables: dict, spec: dict, kind: str = "query") -> str:
    args = ", ".join(f"{name}: {_literal(value)}" for name, value in variables.items())
    return f"{kind} {{ {operation}{f'({args})' if args else ''}{_selection(spec.get('response_schema') or {})} }}"


def classify(response: httpx.Response | None, exc: Exception | None = None) -> Outcome:
    if response is None or exc is not None:
        return Outcome(ErrorClass.E1, "graphql", type(exc).__name__ if exc else "transport")
    code = str(response.status_code)
    if response.status_code == 429 or response.status_code >= 500:
        return Outcome(ErrorClass.E1, "graphql", code)
    try:
        body = response.json()
    except ValueError:
        return Outcome(ErrorClass.E3, "graphql", code)
    errors = body.get("errors", []) if isinstance(body, dict) else []
    data = body.get("data") if isinstance(body, dict) else None
    if errors:
        violations = []
        for error in errors:
            path = error.get("extensions", {}).get("path") or error.get("path")
            if isinstance(path, list):
                violations.append(Violation(Side.REQ, ["body", *path], str(error.get("extensions", {}).get("code", "graphql_error"))))
            elif error.get("extensions", {}).get("code") in ("BAD_USER_INPUT", "GRAPHQL_VALIDATION_FAILED"):
                field = error.get("extensions", {}).get("argument")
                if field:
                    violations.append(Violation(Side.REQ, ["body", field], str(error["extensions"]["code"])))
        cls = ErrorClass.E2 if violations else ErrorClass.BUSINESS
        return Outcome(cls, "graphql", str(errors[0].get("extensions", {}).get("code", "GRAPHQL_ERROR")), data, violations)
    if response.status_code >= 400:
        return Outcome(ErrorClass.E2, "graphql", code, data)
    return Outcome(ErrorClass.OK, "graphql", code, data)


async def send(client: httpx.AsyncClient, doc: dict, timeout: float, *, spec_source=None) -> Outcome:
    """Send using the current schema so response nesting follows the latest introspection."""
    try:
        op = doc.get("operation", doc.get("route", {}).get("operation_id"))
        spec = None
        if spec_source:
            latest = await spec_source()
            spec = latest.ops.get(op)
        spec = spec or doc.get("operation_spec", {})
        variables = doc.get("variables", doc.get("body", {}))
        # shortcut: flat scalar arguments only; use typed GraphQL variables for nested input objects
        if any(isinstance(value, (dict, list)) for value in variables.values()):
            return Outcome(ErrorClass.E3, "graphql", "UNSUPPORTED_ARGUMENT_SHAPE")
        violations = _arg_violations(variables, spec)
        if violations:
            return Outcome(ErrorClass.E2, "graphql", "SCHEMA_VALIDATION", violations=violations)
        kind = doc.get("kind", "query")
        if kind == "query" and spec_source and latest.raw.get("data", {}).get("__schema", {}).get("mutationType", {}).get("name"):
            mutation_root = latest.raw["data"]["__schema"]["mutationType"]["name"]
            if op in {f["name"] for f in next((t["fields"] for t in latest.raw["data"]["__schema"]["types"] if t.get("name") == mutation_root), [])}:
                kind = "mutation"
        query = _query(op, variables, spec, kind)
        path = doc.get("route", {}).get("path", "/graphql")
        response = await client.post(path, json={"query": query}, timeout=timeout)
    except httpx.HTTPError as exc:
        return classify(None, exc)
    except (KeyError, TypeError, ValueError) as exc:
        return Outcome(ErrorClass.E3, "graphql", type(exc).__name__)
    outcome = classify(response)
    if outcome.cls is ErrorClass.OK and isinstance(outcome.data, dict) and op in outcome.data:
        outcome.data = outcome.data[op]
    return outcome
