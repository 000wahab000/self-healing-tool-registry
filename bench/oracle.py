"""Request-level benchmark oracle, independent of the resulting mock state."""

from __future__ import annotations

from typing import Any

from healer.canonical import dumps


def classify_request(
    expected: dict[str, Any], request: dict[str, Any], status: int | None, cfg: dict[str, str]
) -> str:
    """Classify one target request; rejected requests are not false patches."""
    if status is None or not 200 <= status < 300:
        return "REJECTED"
    expected_headers = {
        name.lower(): cfg[value["key"]]
        if isinstance(value, dict) and value.get("ref") == "config"
        else value
        for name, value in expected["headers"].items()
    }
    actual = {
        "method": request["method"],
        "path": request["path"],
        "body": request["body"],
        "query": request.get("query", {}),
        "headers": {
            name: value
            for name, value in request["headers"].items()
            if name in expected_headers
        },
    }
    canonical_expected = {**expected, "headers": expected_headers}
    canonical_expected.pop("must_refuse", None)
    return "CORRECT" if dumps(actual) == dumps(canonical_expected) else "WRONG_ACCEPTED"


def classify_run(
    expected: dict[str, Any], requests: list[dict[str, Any]], received: list[dict[str, Any]], cfg: dict[str, str]
) -> str:
    """Use the target operation's accepted request, including renamed-route attempts."""
    if expected.get("must_refuse"):
        return "REJECTED"
    candidates = [
        (request, result)
        for request, result in zip(requests, received, strict=False)
        if request["method"] == expected["method"]
        and (
            request["path"] == expected["path"]
            or request["body"] == expected["body"]
        )
    ]
    accepted = [(request, result) for request, result in candidates if result["status"] < 300]
    if accepted:
        request, result = accepted[-1]
        request = {**request, "query": result["query"]}
        return classify_request(expected, request, result["status"], cfg)
    return "REJECTED"
