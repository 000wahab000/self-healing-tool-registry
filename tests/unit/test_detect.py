from __future__ import annotations

import httpx
import pytest

from healer import contract, detect
from healer.models import ErrorClass as C
from healer.models import Side

REQ = httpx.Request("POST", "http://mock/x")
BASE = {
    "route": {"method": "POST", "path": "/users/lookup"},
    "body": {"user_id": "123"},
    "query": {},
    "header": {},
}
USER_SCHEMA = {
    "title": "UserOut",
    "type": "object",
    "required": ["id", "name", "email"],
    "properties": {
        "id": {"title": "Id", "type": "string"},
        "name": {"title": "Name", "type": "string"},
        "email": {"title": "Email", "anyOf": [{"type": "string"}, {"type": "null"}]},
    },
}
ECHO_ID = {"type": "echo", "response": ["id"], "request": ["body", "user_id"]}
USER = {"id": "123", "name": "Ada", "email": "ada@example.com"}
DETAIL_422 = [
    {"type": "missing", "loc": ["body", "customer_id"], "msg": "Field required"},
    {"type": "int_type", "loc": ["body", "target", "id"], "msg": "Input should be int"},
]
BEARER = {"WWW-Authenticate": "Bearer"}


def r(status: int, body=None, headers=None) -> httpx.Response:
    return httpx.Response(status, json=body, headers=headers, request=REQ)


def raw(content: bytes, ctype: str) -> httpx.Response:
    return httpx.Response(
        200, content=content, headers={"content-type": ctype}, request=REQ
    )


def raw_status(status: int, content: bytes, ctype: str) -> httpx.Response:
    return httpx.Response(
        status, content=content, headers={"content-type": ctype}, request=REQ
    )


def case(name, resp, cls, code, viol=(), *, exc=None, schema=None, checks=()):
    return pytest.param(resp, exc, schema, list(checks), cls, code, list(viol), id=name)


def req(path, kind):
    return (Side.REQ, path, kind)


CASES = [
    case("ok", r(200, USER), C.OK, "200"),
    case("ok_204", r(204), C.OK, "204"),
    case("ok_empty_error_field", r(200, {**USER, "error": ""}), C.OK, "200"),
    case("business_409", r(409, {"detail": "exists"}), C.BUSINESS, "409"),
    case("e1_exception", None, C.E1, "ReadTimeout", exc=httpx.ReadTimeout("t")),
    case("e1_503", r(503), C.E1, "503"),
    case("e1_429", r(429), C.E1, "429"),
    case(
        "e2_422",
        r(422, {"detail": DETAIL_422}),
        C.E2,
        "422",
        [
            req(["body", "customer_id"], "missing"),
            req(["body", "target", "id"], "int_type"),
        ],
    ),
    case(
        "e2_401_bearer",
        r(401, {"detail": "Not authenticated"}, BEARER),
        C.E2,
        "401",
        [req(["header", "authorization"], "auth")],
    ),
    case("e2_401_plain", r(401), C.E2, "401", [req(["header"], "auth")]),
    case(
        "e2_404",
        r(404, {"detail": "Not Found"}),
        C.E2,
        "404",
        [req(["route"], "route")],
    ),
    case("e2_405", r(405), C.E2, "405", [req(["route"], "route")]),
    case("e2_400", r(400, {"detail": "bad"}), C.E2, "400", [req([], "rejected")]),
    case("e2_422_not_fastapi", r(422, {"oops": 1}), C.E2, "422", [req([], "rejected")]),
    case("e3_html", raw(b"<html></html>", "text/html"), C.E3, "200"),
    case("e3_bad_json", raw(b"{oops", "application/json"), C.E3, "200"),
    case(
        "e4_success_false", r(200, {"success": False, "error": "bad id"}), C.E4, "200"
    ),
    case("e4_status_error", r(200, {"status": "error"}), C.E4, "200"),
    case("e4_errors_list", r(200, {"errors": ["bad id"]}), C.E4, "200"),
    case(
        "e5_missing",
        r(200, {"data": USER}),
        C.E5,
        "200",
        [(Side.RESP, [k], "missing") for k in ("id", "name", "email")],
        schema=USER_SCHEMA,
    ),
    case(
        "e5_type",
        r(200, {**USER, "id": 123}),
        C.E5,
        "200",
        [(Side.RESP, ["id"], "type")],
        schema=USER_SCHEMA,
    ),
    case(
        "ok_schema_null_branch",
        r(200, {**USER, "email": None}),
        C.OK,
        "200",
        schema=USER_SCHEMA,
    ),
    case(
        "e6_echo",
        r(200, {**USER, "id": "999"}),
        C.E6,
        "200",
        [req(["body", "user_id"], "postcheck")],
        schema=USER_SCHEMA,
        checks=[ECHO_ID],
    ),
    case(
        "e6_non_empty",
        r(200, {**USER, "name": ""}),
        C.E6,
        "200",
        [req([], "postcheck")],
        checks=[{"type": "non_empty", "response": ["name"]}],
    ),
    case(
        "ok_postcheck", r(200, USER), C.OK, "200", schema=USER_SCHEMA, checks=[ECHO_ID]
    ),
]


@pytest.mark.parametrize("resp, exc, schema, checks, cls, code, viol", CASES)
def test_ac_03_detector_table(resp, exc, schema, checks, cls, code, viol):
    out = detect.classify(resp, exc)
    out = contract.check(out, output_schema=schema, postchecks=checks, base_doc=BASE)
    assert (out.cls, out.protocol, out.raw_code) == (cls, "rest", code)
    assert [(v.side, v.path, v.kind) for v in out.violations] == viol


SOFT = {"success": False, "error": "x"}


NOT_FOUND = {"detail": "User not found"}


@pytest.mark.parametrize(
    "resp, cls, data",
    [
        (r(200, USER), C.OK, USER),
        (r(204), C.OK, {}),
        (r(200, SOFT), C.E4, SOFT),
        (r(409, {"detail": "exists"}), C.BUSINESS, {"detail": "exists"}),
        (r(404, NOT_FOUND), C.E2, NOT_FOUND),
        (r(422, {"detail": DETAIL_422}), C.E2, {"detail": DETAIL_422}),
        (r(400), C.E2, None),
        (raw_status(400, b"<p>no</p>", "text/html"), C.E2, None),
        (raw_status(409, b"", "application/json"), C.BUSINESS, None),
    ],
)
def test_data_carries_decoded_body(resp, cls, data):
    out = detect.classify(resp)
    assert (out.cls, out.data) == (cls, data)


@pytest.mark.parametrize(
    "headers, data",
    [
        ({"Retry-After": "2"}, {"retry_after": 2.0}),
        ({"Retry-After": "0.5"}, {"retry_after": 0.5}),
        ({"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}, None),
        ({"Retry-After": "-3"}, None),
        ({}, None),
    ],
)
def test_e1_carries_numeric_retry_after(headers, data):
    out = detect.classify(r(503, headers=headers))
    assert (out.cls, out.data) == (C.E1, data)


@pytest.mark.parametrize(
    ("fastapi_type", "kind"),
    [
        ("string_pattern_mismatch", "pattern"),
        ("greater_than", "range"),
        ("greater_than_equal", "range"),
        ("less_than", "range"),
        ("less_than_equal", "range"),
        ("enum", "enum"),
        ("literal_error", "enum"),
        ("value_error", "format"),
        ("string_too_short", "length"),
        ("string_too_long", "length"),
        ("too_short", "length"),
        ("too_long", "length"),
        # structural kinds and anything unknown pass through
        ("missing", "missing"),
        ("int_type", "int_type"),
        ("extra_forbidden", "extra_forbidden"),
    ],
)
def test_fr_3_4_422_types_are_normalised_to_value_kinds(fastapi_type, kind):
    body = {"detail": [{"type": fastapi_type, "loc": ["body", "email"], "msg": "x"}]}
    out = detect.classify(r(422, body))
    assert [(v.side, v.path, v.kind) for v in out.violations] == [
        req(["body", "email"], kind)
    ]
    assert (kind in detect.VALUE_KINDS) == (
        kind not in {"missing", "int_type", "extra_forbidden"}
    )
