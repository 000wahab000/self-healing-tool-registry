"""Response classification (technical-approach 5.1, steps 1-5). Schema and postchecks live in contract.py."""

from __future__ import annotations

import httpx

from healer.models import ErrorClass, Outcome, Side, Violation

PROTOCOL = "rest"
AUTH_STATUSES = (401, 403, 428)
VALUE_KINDS = frozenset({"format", "range", "pattern", "enum", "length"})
_VALUE_TYPES = {
    "string_pattern_mismatch": "pattern",
    "enum": "enum",
    "literal_error": "enum",
    "value_error": "format",
    "string_too_short": "length",
    "string_too_long": "length",
    "too_short": "length",
    "too_long": "length",
}


def _kind(fastapi_type: str) -> str:
    """FR-3.4: a 422 type that says the value is bad becomes a value kind; all others stay as sent."""
    if fastapi_type.startswith(("greater_than", "less_than")):
        return "range"
    return _VALUE_TYPES.get(fastapi_type, fastapi_type)


def _violations(resp: httpx.Response) -> list[Violation]:
    status = resp.status_code
    if status == 422:
        try:
            items = [
                Violation(Side.REQ, list(d["loc"]), _kind(d["type"]))
                for d in resp.json()["detail"]
            ]
        except (ValueError, KeyError, TypeError):
            items = []
        if items:
            return items
    elif status in (404, 405):
        return [Violation(Side.REQ, ["route"], "route")]
    elif status in AUTH_STATUSES:
        bearer = "bearer" in resp.headers.get("www-authenticate", "").lower()
        return [
            Violation(
                Side.REQ, ["header", "authorization"] if bearer else ["header"], "auth"
            )
        ]
    return [Violation(Side.REQ, [], "rejected")]


def _error_body(resp: httpx.Response) -> object:
    """The API's own error detail for the agent; None when the body is not JSON."""
    try:
        return resp.json()
    except ValueError:
        return None


def _retry_after(resp: httpx.Response) -> dict | None:
    value = resp.headers.get("retry-after", "")
    # ponytail: only the delay-seconds form; an HTTP-date is ignored.
    return (
        {"retry_after": float(value)} if value.replace(".", "", 1).isdigit() else None
    )


def _is_soft_error(body: object) -> bool:
    return isinstance(body, dict) and (
        body.get("success") is False
        or body.get("status") in ("error", "fail")
        or bool(body.get("error"))
        or bool(body.get("errors"))
    )


def classify(response: httpx.Response | None, exc: Exception | None = None) -> Outcome:
    if exc is not None or response is None:
        return Outcome(ErrorClass.E1, PROTOCOL, type(exc).__name__)
    status = response.status_code
    code = str(status)
    if status == 429 or status >= 500:
        return Outcome(ErrorClass.E1, PROTOCOL, code, data=_retry_after(response))
    if status == 409:
        return Outcome(ErrorClass.BUSINESS, PROTOCOL, code, _error_body(response))
    if 400 <= status < 500:
        return Outcome(
            ErrorClass.E2,
            PROTOCOL,
            code,
            _error_body(response),
            _violations(response),
        )
    if not response.content:
        return Outcome(ErrorClass.OK, PROTOCOL, code, data={})
    media = response.headers.get("content-type", "").split(";")[0].strip().lower()
    undecodable = Outcome(ErrorClass.E3, PROTOCOL, code)
    if media != "application/json" and not media.endswith("+json"):
        return undecodable
    try:
        body = response.json()
    except ValueError:
        return undecodable
    cls = ErrorClass.E4 if _is_soft_error(body) else ErrorClass.OK
    return Outcome(cls, PROTOCOL, code, data=body)
