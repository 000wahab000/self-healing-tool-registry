"""Response classification (technical-approach 5.1, steps 1-5). Schema and postchecks live in contract.py."""

from __future__ import annotations

import httpx

from healer.models import ErrorClass, Outcome, Side, Violation

PROTOCOL = "rest"
AUTH_STATUSES = (401, 403, 428)


def _violations(resp: httpx.Response) -> list[Violation]:
    status = resp.status_code
    if status == 422:
        try:
            items = [
                Violation(Side.REQ, list(d["loc"]), d["type"])
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
        return Outcome(ErrorClass.E1, PROTOCOL, code)
    if status == 409:
        return Outcome(ErrorClass.BUSINESS, PROTOCOL, code)
    if 400 <= status < 500:
        return Outcome(ErrorClass.E2, PROTOCOL, code, violations=_violations(response))
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
