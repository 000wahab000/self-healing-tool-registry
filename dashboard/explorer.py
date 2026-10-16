"""Explorer module: reference metadata, predefined queries, and detailed schema & trace collection."""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

import httpx

from agents.common import MAX_ITERATIONS
from bench.run import CONTROL_STEPS, CONTROL_TASK
from healer.models import ErrorClass
from healer.openapi_loader import fetch_spec, operations
from healer.registry import Registry, _agent_schema
from healer.repair import from_env as repair_from_env
from healer.store import Store
from mock_api.app import MUTATIONS, SEED

PREDEFINED_QUERIES = [
    {
        "id": "clean",
        "title": "Clean Run (No Mutation)",
        "query": "Look up user 123, change email to ada.new@example.com, set manager to 456, and open support ticket.",
        "mutation": None,
        "tool_affected": None,
        "error_class": "OK",
        "description": "API operates normally on v1 spec. Both agents run cleanly, completing the task with 4 tool calls and correct final data state.",
        "demonstrates": "Normal baseline: input and output schemas match perfectly between agent and API.",
    },
    {
        "id": "m1_rename",
        "title": "Field Rename: user_id → customer_id (M1)",
        "query": "Look up user 123 to verify account profile.",
        "mutation": "M1",
        "tool_affected": "get_user",
        "error_class": "E2",
        "description": "API renamed required input field 'user_id' to 'customer_id' on POST /users/lookup. Server returns 422 Unprocessable Entity.",
        "demonstrates": "Healing Agent detects E2, diffs spec, applies `move body.user_id → body.customer_id`, and recovers. Baseline loops on 422 until the 10-call cap.",
    },
    {
        "id": "m2_type",
        "title": "Type Conversion: user_id str → int (M2)",
        "query": "Update email for user '123' to ada.new@example.com.",
        "mutation": "M2",
        "tool_affected": "update_email",
        "error_class": "E2",
        "description": "API changed 'user_id' from string to strict integer on PATCH /users/email. Server returns 422 type validation error.",
        "demonstrates": "Healing Agent verifies lossless cast, converts '123' to 123, and replays successfully. Baseline loops on 422.",
    },
    {
        "id": "m3_response",
        "title": "Response Nesting: {data: {...}} (M3)",
        "query": "Look up user 123.",
        "mutation": "M3",
        "tool_affected": "get_user",
        "error_class": "E5",
        "description": "API wrapped output in an envelope: {id, name, email} became {data: {id, name, email}}. Returns 200 but violates output contract.",
        "demonstrates": "Healing Agent detects E5 (SHAPE_DRIFT), applies response remap `move data.id→id, data.name→name, data.email→email` in-memory. Baseline returns unmapped envelope to agent.",
    },
    {
        "id": "m4_auth",
        "title": "Mandatory Header: Authorization Bearer (M4)",
        "query": "Open a support ticket for user 123 titled 'Email changed'.",
        "mutation": "M4",
        "tool_affected": "create_ticket",
        "error_class": "E2",
        "description": "API added mandatory OAuth Bearer token requirement on POST /tickets. Server returns 401 Unauthorized with WWW-Authenticate header.",
        "demonstrates": "Healing Agent detects 401, matches security requirement against configured header sources, injects 'Authorization: Bearer test-token', and recovers. Baseline loops on 401.",
    },
    {
        "id": "m5_combined",
        "title": "Combined Drift: Nest + Cast + Tenant Header (M5)",
        "query": "Look up user 123 (Problem Statement §1 Example).",
        "mutation": "M5",
        "tool_affected": "get_user",
        "error_class": "E2",
        "description": "The exact scenario from PS 01: {'user_id':'123'} became {'target':{'id':123}} plus mandatory 'X-Tenant-Id' header.",
        "demonstrates": "Healing Agent synthesizes 3 operations (`move` + `cast` + `header`) in a single tier-1 heal (<1.5s). Baseline fails with 422 loop.",
    },
    {
        "id": "m6_ambiguous",
        "title": "Ambiguous Renames: subject & supervisor (M6-D)",
        "query": "Set manager for user 123 to 456.",
        "mutation": "M6-D",
        "tool_affected": "set_manager",
        "error_class": "E2",
        "description": "API renamed user_id and manager_id to 'subject' and 'supervisor' (no shared substring tokens). Both are string types.",
        "demonstrates": "Deterministic tie-breaker analyzes OpenAPI descriptions ('Employee to update' vs 'Manager to assign') to disambiguate the mapping correctly without needing an LLM.",
    },
    {
        "id": "m6n_ambiguous",
        "title": "Ambiguous Renames, No Descriptions (M6-N)",
        "query": "Set manager for user 123 to 456.",
        "mutation": "M6-N",
        "tool_affected": "set_manager",
        "error_class": "E2",
        "description": "Same rename to 'subject' and 'supervisor', but the new fields carry no descriptions, so nothing tells them apart.",
        "demonstrates": "The tie-breaker cannot decide. Without a confident Jev pick confirmed by a read-only preverify, the write is refused LOW_CONFIDENCE, the manager stays unset, and the agent still opens the ticket.",
    },
    {
        "id": "m7_silent",
        "title": "Silent Drift: email → email_address (M7) [FALSE DATA DEMO]",
        "query": "Update email for user 123 to ada.new@example.com.",
        "mutation": "M7",
        "tool_affected": "update_email",
        "error_class": "E6",
        "description": "API renamed 'email' to optional 'email_address'. Server silently IGNORES unknown 'email' and returns 200 OK without updating database!",
        "demonstrates": "FALSE DATA FED: Baseline receives 200 OK and reports success, but database was NOT updated (email still old)! Healing Agent runs postcheck, catches E6 (SILENT_IGNORE), remaps field to 'email_address', and ensures database is genuinely updated.",
    },
    {
        "id": "m8_refuse",
        "title": "Safe Refusal: Unfillable priority Field (M8)",
        "query": "Open a support ticket titled 'Email changed' for user 123.",
        "mutation": "M8",
        "tool_affected": "create_ticket",
        "error_class": "E2",
        "description": "API added required 'priority' field with no config source and no argument source. Server returns 422.",
        "demonstrates": "SAFE REFUSAL: The registry strictly refuses to heal (NO_SAFE_VALUE) because it never invents, hallucinates, or defaults missing values. The agent is told the tool is unavailable and carries on; nothing is written with an invented value.",
    },
    {
        "id": "m9_wrap",
        "title": "Request Wrapping: payload envelope (M9)",
        "query": "Update email for user 123 to ada.new@example.com.",
        "mutation": "M9",
        "tool_affected": "update_email",
        "error_class": "E2",
        "description": "API wrapped flat request body into nested envelope {payload: {user_id, email}}. Server returns 422.",
        "demonstrates": "Healing Agent detects structural wrapping and moves both fields into 'payload', successfully executing the update.",
    },
    {
        "id": "c1_transient",
        "title": "Control: Transient 503 Service Unavailable (C1)",
        "query": "Look up user 123.",
        "mutation": "C1",
        "tool_affected": "get_user",
        "error_class": "E1",
        "description": "API returns 503 twice, then recovers. This is infrastructure flakiness, NOT schema drift.",
        "demonstrates": "Registry classifies as E1 (TRANSIENT) and applies bounded exponential retry without triggering a schema heal. Both agents recover via retry.",
    },
    {
        "id": "c2_missing_user",
        "title": "Control: Unknown User 404 (C2)",
        "query": CONTROL_TASK["C2"],
        "mutation": "C2",
        "tool_affected": "get_user",
        "error_class": "BUSINESS",
        "description": "The agent asks for user 999, which does not exist. The spec is unchanged, so this is a business error, not drift.",
        "demonstrates": "Registry classifies BUSINESS / NOT_DRIFT and passes the 404 through without healing or replaying.",
    },
    {
        "id": "c3_bad_email",
        "title": "Control: Invalid Email 422 (C3)",
        "query": CONTROL_TASK["C3"],
        "mutation": "C3",
        "tool_affected": "update_email",
        "error_class": "BUSINESS",
        "description": "The agent sends 'not-an-email'. The API answers 422, but the spec is unchanged: the value is wrong, not the schema.",
        "demonstrates": "Registry reclassifies the 422 as BUSINESS / NOT_DRIFT, audits it and returns it unchanged. No patch, no replay.",
    },
    {
        "id": "m10",
        "title": "M10: Prompt-Injection Resistance",
        "query": "Look up user 123.",
        "mutation": "M10",
        "tool_affected": "get_user",
        "error_class": "E2",
        "description": "The 422 error and OpenAPI description contain prompt injections. Registry ignores the prompts and heals via move.",
        "demonstrates": "Adversarial resistance (S8 / AC-26): prompt injection in error body or spec is completely ignored.",
    },
    {
        "id": "m11",
        "title": "M11: Moved and renamed (LLM repair)",
        "query": "Look up user 123.",
        "mutation": "M11",
        "tool_affected": "get_user",
        "error_class": "E2",
        "description": "get_user became find_customer at a new route, and user_id became customer_id. Tier 1 finds no evidence that pairs them.",
        "demonstrates": "Tier 2: the LLM repair agent proposes a fix from the spec, checked by the same safety gate and verified live. Needs NVIDIA_API_KEY.",
    },
    {
        "id": "w1_no_save",
        "title": "Accepted Write, No Save (W1)",
        "query": "Update user 123's email to ada.new@example.com.",
        "mutation": "W1",
        "tool_affected": "update_email",
        "error_class": "E6",
        "description": "The API accepts the email update with HTTP 200 but silently does not save it.",
        "demonstrates": "The declared postcheck detects the missing state change (E6); replaying the same request cannot repair this mutation, so do not claim a successful heal.",
    },
    {
        "id": "u1_amount_units",
        "title": "Schema-Valid Amount Units (U1)",
        "query": "Create a payment for 1250 cents.",
        "mutation": "U1",
        "tool_affected": "create_payment",
        "error_class": "OK",
        "description": "The payment endpoint accepts the schema-valid integer amount_cents, but returns 100 times that value.",
        "demonstrates": "This is a semantic unit mismatch, not schema drift. create_payment is not in the default demo tool configuration, so the default explorer run cannot call or heal it.",
    },
    {
        "id": "d1_side_effect_503",
        "title": "Side Effect Before 503 (D1)",
        "query": "Open a support ticket for user 123 titled 'Email changed'.",
        "mutation": "D1",
        "tool_affected": "create_ticket",
        "error_class": "E1",
        "description": "The API creates the ticket and then returns HTTP 503, so the side effect has already happened when the transient error reaches the caller.",
        "demonstrates": "A 503 is classified as E1, not schema drift. The explorer must not suggest a schema heal; retries risk repeating a write that already took effect.",
    },
]

# Banner per scenario: what the agent sends (v1), what the drifted API wants, what should happen.
DRIFT = {
    None: ('{"user_id": "123"}', "No change: the API still serves v1", "Both agents finish all 4 steps"),
    "M1": ('{"user_id": "123"}', '{"customer_id": "123"}', "Heal: MOVE user_id → customer_id"),
    "M2": ('{"user_id": "123", "email": …}', '{"user_id": 123, "email": …}', "Heal: CAST user_id → int"),
    "M3": ('→ {"id", "name", "email"}', '→ {"data": {"id", "name", "email"}}  (200 OK)', "Catch 200 OK shape drift (E5), un-nest with response MOVE ×3"),
    "M4": ("POST /tickets  (no auth)", "Authorization: Bearer … required  (401)", "Heal: HEADER Authorization ← config:OAUTH_BEARER"),
    "M5": ('{"user_id": "123"}', '{"target": {"id": 123}}  + header X-Tenant-Id', "Heal: MOVE + CAST + HEADER in one tier-1 patch"),
    "M6-D": ('{"user_id", "manager_id"}', '{"subject", "supervisor"}  (described)', "Tie-breaker picks the mapping from field descriptions, 0 AI calls"),
    "M6-N": ('{"user_id", "manager_id"}', '{"subject", "supervisor"}  (no descriptions)', "Refuse LOW_CONFIDENCE: no write on a guess, then finish the other steps"),
    "M7": ('{"email": "ada.new@…"}', '{"email_address": …}  old field silently ignored, 200 OK', "Echo postcheck catches E6, MOVE email → email_address"),
    "M8": ('{"user_id", "title"}', '{"user_id", "title", "priority"}  priority required', "Refuse NO_SAFE_VALUE (retry: false): skip the tool, never invent priority"),
    "M9": ('{"user_id", "email"}', '{"payload": {"user_id", "email"}}', "Heal: MOVE ×2 into payload"),
    "M10": ('{"user_id": "123"}', '{"customer_id": "123"} (injected desc)', "Heal: MOVE user_id → customer_id, injection ignored"),
    "M11": ("POST /users/lookup {\"user_id\"}", "POST /customers/lookup {\"customer_id\"}  (find_customer)", "Rules can't pair a moved and renamed tool: Jev triage, then the LLM repair agent proposes ROUTE + MOVE"),
    "W1": ('{"user_id": "123", "email": "ada.new@example.com"}', "HTTP 200; email remains unchanged", "Detect E6 (no save); replay does not make this mutation save the email"),
    "U1": ('{"amount_cents": 1250}', "Schema accepts the integer; response amount_cents is 125000", "Semantic units mismatch, not schema drift; create_payment is not configured in the default explorer"),
    "D1": ('POST /tickets {"user_id": "123", "title": "Email changed"}', "Ticket is created, then HTTP 503", "E1 transient error after a write; no schema heal, and retrying risks a duplicate side effect"),
    "C1": ("200 OK", "503 twice, then OK", "Not drift: bounded retry, no patch"),
    "C2": ('{"user_id": "999"}', "404 User not found  (spec unchanged)", "Business error passed through (NOT_DRIFT), no patch"),
    "C3": ('{"email": "not-an-email"}', "422 invalid email  (spec unchanged)", "Business error passed through (NOT_DRIFT), no replay"),
}
for _p in PREDEFINED_QUERIES:
    _p["before"], _p["after"], _p["expect"] = DRIFT[_p["mutation"]]
# Mock request headers that only describe the transport, not the drift.
TRANSPORT_HEADERS = {"host", "accept", "accept-encoding", "connection", "user-agent", "content-length", "content-type"}

ERROR_CLASSES = [
    {
        "code": "OK",
        "name": "OK",
        "description": "All HTTP, contract, and postchecks passed successfully.",
        "action": "Return verified result to the agent.",
        "badge_color": "var(--ok)",
    },
    {
        "code": "BUSINESS",
        "name": "Business Error",
        "description": "Legitimate business rejections (409 conflict, 404 for missing records, or 4xx value validation errors when spec diff is empty).",
        "action": "Pass through unchanged to agent. NEVER heal business errors.",
        "badge_color": "var(--biz)",
    },
    {
        "code": "E1",
        "name": "Transient (5xx / 429 / Timeout)",
        "description": "Temporary service disruption, gateway timeouts, rate limiting, or connection resets.",
        "action": "Bounded exponential retry (up to 3x with jitter). NEVER heal.",
        "badge_color": "var(--e1)",
    },
    {
        "code": "E2",
        "name": "Request Rejected (4xx)",
        "description": "Server rejected request format or payload (422 Unprocessable, 400 Bad Request, 401 Unauthorized, 404 route drift).",
        "action": "Trigger Tier-1 Heal on request side (spec diff + error clues → patch → replay once).",
        "badge_color": "var(--e2)",
    },
    {
        "code": "E3",
        "name": "Undecodable Body",
        "description": "Server returned malformed, non-JSON or HTML error body instead of expected JSON.",
        "action": "Return structured error UNSUPPORTED_CLASS with retry: false. No replay.",
        "badge_color": "var(--e3)",
    },
    {
        "code": "E4",
        "name": "Soft Error (Error in 2xx)",
        "description": "Server responded with HTTP 200/201 but body contains an error payload (e.g. GraphQL-style {errors: [...]}).",
        "action": "Heal request side. Replay only if tool is idempotent or has Idempotency-Key.",
        "badge_color": "var(--e4)",
    },
    {
        "code": "E5",
        "name": "Shape Drift (Response Drift)",
        "description": "Server returned 2xx but response body violates agent-facing output schema (e.g. nested envelope, renamed fields).",
        "action": "Heal response side in-memory via remap operations. No network replay needed.",
        "badge_color": "var(--e5)",
    },
    {
        "code": "E6",
        "name": "Silent Ignore (Postcheck Failure)",
        "description": "Server returned 2xx and valid shape, but silently ignored input fields without persisting state (e.g. unannounced deprecation).",
        "action": "Detected by contract postchecks. Heal request side and replay if safe.",
        "badge_color": "var(--e6)",
    },
]

MOCK_INFO = {
    "title": "Mock Drift API",
    "description": "Deterministic in-process FastAPI service serving OpenAPI 3.x spec, strict validation, and runtime mutation switching.",
    "tools": {
        "get_user": {
            "method": "POST",
            "path": "/users/lookup",
            "description": "Look up user details by user ID.",
            "idempotent": True,
            "write": False,
            "postchecks": [{"type": "echo", "response": ["id"], "request": ["body", "user_id"]}],
            "v1_input": {
                "type": "object",
                "properties": {"user_id": {"type": "string", "description": "User identifier"}},
                "required": ["user_id"],
            },
            "v1_output": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "email": {"type": "string"},
                },
                "required": ["id", "name", "email"],
            },
        },
        "update_email": {
            "method": "PATCH",
            "path": "/users/email",
            "description": "Update user email address.",
            "idempotent": True,
            "write": True,
            "postchecks": [
                {"type": "echo", "response": ["id"], "request": ["body", "user_id"]},
                {"type": "echo", "response": ["email"], "request": ["body", "email"]},
            ],
            "v1_input": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User identifier"},
                    "email": {"type": "string", "format": "email", "description": "New email address"},
                },
                "required": ["user_id", "email"],
            },
            "v1_output": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "email": {"type": "string"},
                },
                "required": ["id", "email"],
            },
        },
        "set_manager": {
            "method": "POST",
            "path": "/users/manager",
            "description": "Assign manager to a user.",
            "idempotent": True,
            "write": True,
            "preverify": {"method": "POST", "path": "/users/manager/validate"},
            "postchecks": [
                {"type": "echo", "response": ["id"], "request": ["body", "user_id"]},
                {"type": "echo", "response": ["manager_id"], "request": ["body", "manager_id"]},
            ],
            "v1_input": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "Employee to update"},
                    "manager_id": {"type": "string", "description": "Manager to assign"},
                },
                "required": ["user_id", "manager_id"],
            },
            "v1_output": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "manager_id": {"type": "string"},
                },
                "required": ["id", "manager_id"],
            },
        },
        "create_ticket": {
            "method": "POST",
            "path": "/tickets",
            "description": "Open a support ticket on behalf of a user.",
            "idempotent": False,
            "idempotency_key": True,
            "write": True,
            "postchecks": [
                {"type": "non_empty", "response": ["ticket_id"]},
                {"type": "echo", "response": ["user_id"], "request": ["body", "user_id"]},
            ],
            "v1_input": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User identifier"},
                    "title": {"type": "string", "description": "Ticket summary title"},
                },
                "required": ["user_id", "title"],
            },
            "v1_output": {
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string"},
                    "user_id": {"type": "string"},
                    "title": {"type": "string"},
                },
                "required": ["ticket_id", "user_id", "title"],
            },
        },
    },
    "seed_data": SEED,
    "header_sources": {
        "Authorization": "OAUTH_BEARER (configured value: 'Bearer test-token')",
        "X-Tenant-Id": "TENANT_ID (configured value: 't-1')",
    },
}


def get_explorer_info() -> dict:
    return {
        "mock_info": MOCK_INFO,
        "predefined_queries": PREDEFINED_QUERIES,
        "error_classes": ERROR_CLASSES,
        "mutations": list(MUTATIONS),
        "llm_available": bool(os.environ.get("NVIDIA_API_KEY")),
        "llm_model": os.environ.get("LLM_MODEL", "openai/gpt-oss-20b"),
    }


def extract_tool_schemas(resolved_spec: dict, tools_config: dict) -> dict[str, dict]:
    """Extract input and output schemas from a resolved OpenAPI spec for each configured tool."""
    ops = operations(resolved_spec)
    result = {}
    for name in tools_config.get("tools", {}):
        op = ops.get(name)
        if not op:
            continue
        in_schema = _agent_schema(op)
        out_schema = op.get("response_schema") or {"type": "object", "properties": {}}
        result[name] = {
            "method": op["method"],
            "path": op["path"],
            "input_schema": in_schema,
            "output_schema": out_schema,
            "security": op.get("security", []),
        }
    return result


def check_data_correctness(
    data: dict, mutation: str | None, touched: set | None = None
) -> tuple[bool, dict]:
    """Verify mock API state against expected values.

    `touched` restricts the verdict to the tools the run actually called, so a
    live LLM given a one-line request is not failed for work it never asked for.
    An empty/None set means the full four-step demo task.
    """
    full = touched is None
    check_email = full or "update_email" in touched
    check_manager = full or "set_manager" in touched
    check_tickets = full or "create_ticket" in touched

    user = data.get("users", {}).get("123", {})
    tickets = data.get("tickets", [])
    email = user.get("email")
    manager = user.get("manager_id")

    # C2/C3: a business error passed through must leave the data as seeded.
    control = mutation in CONTROL_STEPS
    want_email = SEED["users"]["123"]["email"] if control else "ada.new@example.com"
    email_ok = email == want_email
    # M6-N: set_manager was aborted, so the manager must still be unset.
    manager_ok = (manager is None) if mutation == "M6-N" or control else (manager == "456")
    # M8: the registry safely refused to invent a ticket, so none may exist.
    ticket_ok = (
        (len(tickets) == 0)
        if mutation == "M8" or control
        else (len(tickets) > 0 and any(t.get("title") == "Email changed" for t in tickets))
    )

    # An entity nobody was asked to change cannot make the run incorrect.
    all_ok = (
        (email_ok or not check_email)
        and (manager_ok or not check_manager)
        and (ticket_ok or not check_tickets)
    )

    details = {
        "email": {
            "value": email,
            "expected": want_email,
            "ok": email_ok,
            "checked": check_email,
        },
        "manager": {
            "value": manager,
            "expected": "None" if mutation == "M6-N" or control else "456",
            "ok": manager_ok,
            "checked": check_manager,
        },
        "tickets": {
            "count": len(tickets),
            "expected": 0 if mutation == "M8" or control else 1,
            "ok": ticket_ok,
            "checked": check_tickets,
        },
        "is_correct": all_ok,
        "tools_called": sorted(touched) if touched is not None else [],
    }
    return all_ok, details


def _short_error(error: str | None, limit: int = 300) -> str | None:
    """Provider errors arrive as a page of JSON; the UI only needs the headline."""
    if not error:
        return None
    flat = " ".join(str(error).split())
    return flat if len(flat) <= limit else flat[:limit] + " …"


def _lossless_coerce(value: Any, expected: str) -> Any:
    """Cast a value to the type the frozen v1 schema declares, only if lossless."""
    if expected == "string":
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return str(value)
    elif expected in ("integer", "number") and isinstance(value, str):
        try:
            return int(value) if expected == "integer" else float(value)
        except ValueError:
            return value
    return value


def _coerce_args(name: str, args: dict, tool_schemas: dict) -> tuple[dict, list]:
    """Fit LLM-supplied arguments to the frozen agent-facing schema.

    A live model writes `{"user_id": 123}` where v1 declares a string. The
    registry rejects that as AGENT_ARG_ERROR before anything leaves the process,
    which would hide the drift this tab exists to show. Only lossless casts are
    applied, and every one is reported so the trace never hides what the model did.
    """
    props = (tool_schemas.get(name, {}).get("agent_input") or {}).get("properties", {})
    out = {}
    adjusted = []
    for key, value in (args or {}).items():
        expected = (props.get(key) or {}).get("type")
        cast = _lossless_coerce(value, expected) if expected else value
        if cast != value:
            adjusted.append({"field": key, "from": value, "to": cast})
        out[key] = cast
    return out, adjusted


def _json_or_text(text: str) -> Any:
    """Parse a JSON payload; keep the raw text when it is not JSON."""
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return text


def _parse_tool_result(text: str) -> Any:
    """Baseline tools answer with raw `HTTP n: body`; healers answer with JSON."""
    if text.startswith("HTTP "):
        status, _, body = text.removeprefix("HTTP ").partition(": ")
        try:
            status_code = int(status)
        except ValueError:
            return text
        return {"status_code": status_code, "body": _json_or_text(body)}
    return _json_or_text(text)


def _wire(requests: list[dict]) -> list[dict]:
    """What actually reached the mock API during one call. Header values are never shown."""
    return [
        {
            "method": r["method"],
            "path": r["path"],
            "body": r["body"],
            "headers": sorted(h for h in r["headers"] if h not in TRANSPORT_HEADERS),
        }
        for r in requests
    ]


def _registry(reg: Registry) -> dict:
    """Read-only view of every ToolDefinition after the run."""
    return {
        name: {
            "version": d.version,
            "agent_schema": d.agent_schema,
            "fix": {
                "request_ops": d.active_fix.request_ops,
                "response_ops": d.active_fix.response_ops,
            }
            if d.active_fix
            else None,
        }
        for name, d in reg.defs.items()
    }


def _heal_info(heals: list, store: Store) -> dict | None:
    """The heal the registry performed during one call, if it performed one."""
    if not heals:
        return None
    e = heals[-1]
    fix = store.get_fix(e.fix_id) if e.fix_id is not None else None
    return {
        "tool": e.tool,
        "class": e.cls.value,
        "raw_code": e.raw_code,
        "tier": e.tier.value,
        "path": e.path.value if e.path else None,
        "outcome": e.outcome.value,
        "reason": e.reason.value if e.reason else None,
        "mttr_ms": e.mttr_ms,
        "heal_ms": e.heal_ms,
        "fix": {
            "request_ops": fix.request_ops,
            "response_ops": fix.response_ops,
        }
        if fix
        else None,
    }


def _heal_summaries(store: Store, events: list) -> list:
    """Audit events as the explorer renders them, for a whole run."""
    out = []
    for e in events:
        fix = store.get_fix(e.fix_id) if e.fix_id is not None else None
        out.append(
            {
                "ts_ms": e.ts_ms,
                "tool": e.tool,
                "class": e.cls.value,
                "raw_code": e.raw_code,
                "tier": e.tier.value,
                "path": e.path.value if e.path else None,
                "outcome": e.outcome.value,
                "reason": e.reason.value if e.reason else None,
                "mttr_ms": e.mttr_ms,
                "fix": {
                    "request_ops": fix.request_ops,
                    "response_ops": fix.response_ops,
                }
                if fix
                else None,
            }
        )
    return out


def _llm_bootstrap_error(query, mutation, tool_schemas, healing_traces, baseline_traces, exc):
    """Response for a live-LLM run that could not even reach the provider.

    Returning the failure (instead of falling back to the scripted sequence)
    keeps the demo honest: a red status means no model ran.
    """
    message = _short_error(f"{type(exc).__name__}: {exc}")
    side = lambda traces: {
        "traces": traces,
        "heals": [],
        "status": "error",
        "hit_limit": False,
        "tool_calls": 0,
        "data_state": None,
        "data_correct": False,
        "correctness_details": None,
        "final_text": None,
        "llm_tokens": 0,
        "error": message,
    }
    return {
        "query": query,
        "mutation": mutation,
        "agent": "llm",
        "preset_info": next((p for p in PREDEFINED_QUERIES if p["mutation"] == mutation), None),
        "tool_schemas": tool_schemas,
        "healing": side(healing_traces),
        "baseline": side(baseline_traces),
    }


def _recording_executor(execute, store: Store, tool_schemas: dict, mock):
    """Wrap an Execute so every call, whatever the LLM decides to call, is traced.

    Repeated (tool, args) pairs are flagged so the blind-retry loop a standard
    framework falls into stays visible next to the healing agent's one-shot replay.
    """
    traces: list[dict] = []
    state = {"last": None, "retries": 0}

    async def recording(name: str, args: dict) -> tuple[str, ErrorClass]:
        sent_args, coerced = _coerce_args(name, args, tool_schemas)
        key = (name, json.dumps(sent_args, sort_keys=True, default=str))
        state["retries"] = state["retries"] + 1 if key == state["last"] else 0
        state["last"] = key
        prev_heals = len(store.audit_events())
        sent = len(mock.requests)
        t0 = time.perf_counter()
        text, cls = await execute(name, dict(sent_args))
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        heal_event = _heal_info(store.audit_events()[prev_heals:], store)
        schema = tool_schemas.get(name, {})
        traces.append(
            {
                "step": len(traces) + 1,
                "tool": name,
                "args": args,
                "sent_args": sent_args,
                "coerced": coerced,
                "is_retry": state["retries"] > 0,
                "retry_count": state["retries"],
                "input_schema": schema.get("agent_input", {}),
                "actual_input_schema": schema.get("actual_input", {}),
                "output_schema": schema.get("expected_output", {}),
                "actual_output_schema": schema.get("actual_output", {}),
                "input_drift": schema.get("input_drift", False),
                "output_drift": schema.get("output_drift", False),
                "error_class": cls.value,
                "heal_event": heal_event,
                "result": _parse_tool_result(text),
                "wire": _wire(mock.requests[sent:]),
                "latency_ms": elapsed_ms,
            }
        )
        return text, cls

    return recording, traces


async def run_explore(
    healing_mock,
    baseline_mock,
    store: Store,
    tools_config: dict,
    cfg: dict,
    jev,
    mutation: str | None,
    query: str,
    agent: str = "scripted",
    custom: dict | None = None,
) -> dict:
    """Run both agents synchronously, capturing full per-call traces, schemas, and verification."""
    from langgraph.prebuilt import create_react_agent

    from agents import baseline_agent, common, healing_agent, scripted

    # Validate agent value
    if agent not in ("scripted", "llm"):
        raise ValueError(f"unknown agent '{agent}'")

    # Step A: Reset both mocks to clean v1 state
    healing_mock.reset()
    baseline_mock.reset()

    http_healing = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=healing_mock), base_url="http://mock"
    )
    http_baseline = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=baseline_mock), base_url="http://mock"
    )

    try:
        # Step B: Registries load the clean v1 OpenAPI spec (establishing frozen agent_schema)
        healing_reg = Registry(http_healing, tools_config, cfg, store, jev, repair=repair_from_env())
        baseline_reg = Registry(http_baseline, tools_config, cfg)
        await healing_reg.load()
        await baseline_reg.load()

        # Step C: Runtime schema drift occurs — activate the mutation on both mocks!
        if mutation:
            healing_mock.set_mutation(mutation, custom)
            baseline_mock.set_mutation(mutation, custom)

        # Step D: Extract wire schemas from the mutated API to inspect runtime drift
        mutated_spec, _ = await fetch_spec(http_healing)
        mutated_schemas = extract_tool_schemas(mutated_spec, tools_config)

        tool_schemas = {}
        for name, tool_def in MOCK_INFO["tools"].items():
            actual = mutated_schemas.get(name, {})
            # Use the registry's frozen schemas as the true v1 baseline
            reg_def = healing_reg.defs.get(name)
            v1_in = reg_def.agent_schema if reg_def else tool_def["v1_input"]
            v1_out = reg_def.output_schema if (reg_def and reg_def.output_schema is not None) else tool_def["v1_output"]

            in_schema = actual.get("input_schema", v1_in)
            out_schema = actual.get("output_schema", v1_out)
            tool_schemas[name] = {
                "method": tool_def["method"],
                "path": tool_def["path"],
                "description": tool_def["description"],
                "agent_input": v1_in,
                "actual_input": in_schema,
                "expected_output": v1_out,
                "actual_output": out_schema,
                "input_drift": (v1_in != in_schema),
                "output_drift": (v1_out != out_schema),
                "security": actual.get("security", []),
            }

        # Determine which mode to run
        if agent == "llm":
            # Live mode: the real NVIDIA NIM model decides which tools to call.
            if not os.environ.get("NVIDIA_API_KEY"):
                raise ValueError("llm agents need NVIDIA_API_KEY")

            run_id = uuid.uuid4().hex[:8]
            task = query or CONTROL_TASK.get(mutation, common.TASK)
            base_heal_count = len(store.audit_events())

            heal_execute, healing_traces = _recording_executor(
                healing_agent.executor(healing_reg), store, tool_schemas, healing_mock
            )
            base_execute, baseline_traces = _recording_executor(
                baseline_agent.executor(http_baseline, baseline_reg),
                store,
                tool_schemas,
                baseline_mock,
            )
            try:
                # Same graph the Live tab runs, only the executors are traced.
                llm = common.make_llm()
                heal_graph = create_react_agent(
                    llm,
                    common.make_tools(healing_reg, heal_execute, "healing", store, run_id),
                    prompt=common.SYSTEM_PROMPT,
                )
                base_graph = create_react_agent(
                    llm,
                    common.make_tools(baseline_reg, base_execute, "baseline", store, run_id),
                    prompt=common.SYSTEM_PROMPT,
                )
            except Exception as exc:  # noqa: BLE001  bad key, provider down, cap, ...
                # Report the failure honestly instead of degrading to canned data.
                return _llm_bootstrap_error(
                    query, mutation, tool_schemas, healing_traces, baseline_traces, exc
                )
            # Sequential so the two traces and the shared audit log stay readable.
            healing_result = await common.run(heal_graph, task)
            baseline_result = await common.run(base_graph, task)

            run_heals = _heal_summaries(store, store.audit_events()[base_heal_count:])
            healing_data = healing_mock.state()
            baseline_data = baseline_mock.state()
            healing_touched = {t["tool"] for t in healing_traces}
            baseline_touched = {t["tool"] for t in baseline_traces}
            healing_correct, healing_details = check_data_correctness(
                healing_data, mutation, healing_touched
            )
            baseline_correct, baseline_details = check_data_correctness(
                baseline_data, mutation, baseline_touched
            )
            preset_info = next(
                (p for p in PREDEFINED_QUERIES if p["mutation"] == mutation), None
            )

            def _status(result) -> str:
                if result.error:
                    return "error"
                return "iteration_cap" if result.hit_limit else "done"

            return {
                "query": query,
                "mutation": mutation,
                "agent": "llm",
                "preset_info": preset_info,
                "tool_schemas": tool_schemas,
                "registry": _registry(healing_reg),
                "healing": {
                    "traces": healing_traces,
                    "heals": run_heals,
                    "status": _status(healing_result),
                    "tool_calls": healing_result.tool_calls or len(healing_traces),
                    "data_state": healing_data,
                    "data_correct": healing_correct,
                    "correctness_details": healing_details,
                    "final_text": healing_result.final_text,
                    "llm_tokens": healing_result.llm_tokens,
                    "hit_limit": healing_result.hit_limit,
                    "error": _short_error(healing_result.error),
                },
                "baseline": {
                    "traces": baseline_traces,
                    "heals": [],
                    "status": _status(baseline_result),
                    "tool_calls": baseline_result.tool_calls or len(baseline_traces),
                    "data_state": baseline_data,
                    "data_correct": baseline_correct,
                    "correctness_details": baseline_details,
                    "final_text": baseline_result.final_text,
                    "llm_tokens": baseline_result.llm_tokens,
                    "hit_limit": baseline_result.hit_limit,
                    "error": _short_error(baseline_result.error),
                },
            }

        else:
            # agent == "scripted": keep exact current behavior
            # Step E: Run Healing Agent with call-level tracing
            healing_traces = []
            base_heal_count = len(store.audit_events())
            execute_healing = healing_agent.executor(healing_reg)

            steps = CONTROL_STEPS.get(mutation, scripted.STEPS)
            for call_step, (name, args) in enumerate(steps, start=1):
                t0 = time.perf_counter()
                prev_heals = len(store.audit_events())
                sent = len(healing_mock.requests)
                text, cls = await execute_healing(name, dict(args))
                elapsed_ms = round((time.perf_counter() - t0) * 1000)

                current_heals = store.audit_events()
                heal_info = None
                if len(current_heals) > prev_heals:
                    last_heal = current_heals[-1]
                    fix_record = store.get_fix(last_heal.fix_id) if last_heal.fix_id is not None else None
                    heal_info = {
                        "tool": last_heal.tool,
                        "class": last_heal.cls.value,
                        "raw_code": last_heal.raw_code,
                        "tier": last_heal.tier.value,
                        "path": last_heal.path.value if last_heal.path else None,
                        "outcome": last_heal.outcome.value,
                        "reason": last_heal.reason.value if last_heal.reason else None,
                        "mttr_ms": last_heal.mttr_ms,
                        "heal_ms": last_heal.heal_ms,
                        "fix": {
                            "request_ops": fix_record.request_ops,
                            "response_ops": fix_record.response_ops,
                        } if fix_record else None,
                    }

                parsed_res = _json_or_text(text)

                healing_traces.append({
                    "step": call_step,
                    "tool": name,
                    "args": args,
                    "input_schema": tool_schemas[name]["agent_input"],
                    "actual_input_schema": tool_schemas[name]["actual_input"],
                    "output_schema": tool_schemas[name]["expected_output"],
                    "actual_output_schema": tool_schemas[name]["actual_output"],
                    "input_drift": tool_schemas[name]["input_drift"],
                    "output_drift": tool_schemas[name]["output_drift"],
                    "error_class": cls.value,
                    "heal_event": heal_info,
                    "result": parsed_res,
                    "wire": _wire(healing_mock.requests[sent:]),
                    "latency_ms": elapsed_ms,
                })

                # A refused tool is skipped; the agent carries on (agents/scripted.py does too).

            # Step F: Run Baseline Agent with call-level tracing
            baseline_traces = []
            execute_baseline = baseline_agent.executor(http_baseline, baseline_reg)
            base_step = 0
            hit_limit = False

            for name, args in steps:
                step_retries = 0
                while True:
                    base_step += 1
                    if base_step > MAX_ITERATIONS:
                        hit_limit = True
                        break

                    t0 = time.perf_counter()
                    sent = len(baseline_mock.requests)
                    text, cls = await execute_baseline(name, dict(args))
                    elapsed_ms = round((time.perf_counter() - t0) * 1000)

                    try:
                        if text.startswith("HTTP "):
                            parts = text.split(": ", 1)
                            status_str = parts[0].replace("HTTP ", "")
                            body_str = parts[1] if len(parts) > 1 else ""
                            parsed_body = _json_or_text(body_str)
                            parsed_res = {"status_code": int(status_str), "body": parsed_body}
                        else:
                            parsed_res = _json_or_text(text)
                    except ValueError:  # a status code that is not a number
                        parsed_res = text

                    baseline_traces.append({
                        "step": base_step,
                        "tool": name,
                        "args": args,
                        "is_retry": step_retries > 0,
                        "retry_count": step_retries,
                        "input_schema": tool_schemas[name]["agent_input"],
                        "actual_input_schema": tool_schemas[name]["actual_input"],
                        "output_schema": tool_schemas[name]["expected_output"],
                        "actual_output_schema": tool_schemas[name]["actual_output"],
                        "input_drift": tool_schemas[name]["input_drift"],
                        "output_drift": tool_schemas[name]["output_drift"],
                        "error_class": cls.value,
                        "heal_event": None,  # Baseline has NO healing!
                        "result": parsed_res,
                        "wire": _wire(baseline_mock.requests[sent:]),
                        "latency_ms": elapsed_ms,
                    })

                    if cls is ErrorClass.OK:
                        break

                    step_retries += 1
                    if base_step >= MAX_ITERATIONS:
                        hit_limit = True
                        break

                if hit_limit:
                    break

        # Step G: Collect data states and correctness
        healing_data = healing_mock.state()
        baseline_data = baseline_mock.state()

        healing_correct, healing_details = check_data_correctness(healing_data, mutation)
        baseline_correct, baseline_details = check_data_correctness(baseline_data, mutation)

        run_heals = []
        for e in store.audit_events()[base_heal_count:]:
            fix = store.get_fix(e.fix_id) if e.fix_id is not None else None
            run_heals.append({
                "ts_ms": e.ts_ms,
                "tool": e.tool,
                "class": e.cls.value,
                "raw_code": e.raw_code,
                "tier": e.tier.value,
                "path": e.path.value if e.path else None,
                "outcome": e.outcome.value,
                "reason": e.reason.value if e.reason else None,
                "mttr_ms": e.mttr_ms,
                "fix": {
                    "request_ops": fix.request_ops,
                    "response_ops": fix.response_ops,
                } if fix else None,
            })

        preset_info = next((p for p in PREDEFINED_QUERIES if p["mutation"] == mutation), None)

        return {
            "query": query,
            "mutation": mutation,
            "agent": agent,
            "preset_info": preset_info,
            "tool_schemas": tool_schemas,
            "registry": _registry(healing_reg),
            "healing": {
                "traces": healing_traces,
                "heals": run_heals,
                "status": "done"
                if healing_correct
                else "refused"
                if any(h["outcome"] == "ABORTED" for h in run_heals)
                else "incomplete",
                "tool_calls": len(healing_traces),
                "data_state": healing_data,
                "data_correct": healing_correct,
                "correctness_details": healing_details,
            },
            "baseline": {
                "traces": baseline_traces,
                "heals": [],
                "status": "iteration_cap" if hit_limit else "done",
                "hit_limit": hit_limit,
                "tool_calls": len(baseline_traces),
                "data_state": baseline_data,
                "data_correct": baseline_correct,
                "correctness_details": baseline_details,
            },
        }

    finally:
        await http_healing.aclose()
        await http_baseline.aclose()
