from __future__ import annotations

from fixtures_ops import (
    CREATE_TICKET,
    GET_USER,
    INT,
    MUTATIONS,
    SET_MANAGER,
    STR,
    UPDATE_EMAIL,
    make_op,
    obj,
    param,
)

from healer.diagnose import (
    diff,
    diff_signature,
    flatten_request,
    flatten_response,
    route_exists,
)


def leaf(path: list[str], type_: str, required: bool, description: str = "") -> dict:
    return {
        "path": path,
        "type": type_,
        "required": required,
        "description": description,
    }


def test_flatten_request_leaves_across_locations() -> None:
    body = obj(
        {
            "a": obj({"b": INT, "c": STR}, required=["b"]),
            "opt": obj({"d": STR}),
            "tags": {"type": "array", "items": STR},
            "meta": {"type": "object"},
            "nick": {"anyOf": [STR, {"type": "null"}], "description": "alias"},
            "ver": {"type": ["integer", "null"]},
        },
        required=["a", "tags", "meta"],
    )
    op = make_op(
        "x",
        "POST",
        "/x",
        body,
        None,
        params=[
            param("X-Tenant-Id", "header"),
            param("limit", "query", {"anyOf": [INT, {"type": "null"}]}, False),
            {**param("id", "path"), "description": "ignored"},
        ],
        security=["bearer"],
    )
    assert flatten_request(op) == {
        ("body", "a", "b"): leaf(["body", "a", "b"], "int", True),
        ("body", "a", "c"): leaf(["body", "a", "c"], "str", False),
        ("body", "opt", "d"): leaf(["body", "opt", "d"], "str", False),
        ("body", "tags"): leaf(["body", "tags"], "arr", True),
        ("body", "meta"): leaf(["body", "meta"], "obj", True),
        ("body", "nick"): leaf(["body", "nick"], "str", False, "alias"),
        ("body", "ver"): leaf(["body", "ver"], "int", False),
        ("header", "x-tenant-id"): leaf(["header", "x-tenant-id"], "str", True),
        ("query", "limit"): leaf(["query", "limit"], "int", False),
        ("header", "authorization"): leaf(["header", "authorization"], "str", True),
    }


def test_flatten_request_param_description_and_no_body() -> None:
    p = {**param("limit", "query", INT, False), "description": "page size"}
    op = make_op("x", "GET", "/x", None, None, params=[p])
    assert flatten_request(op) == {
        ("query", "limit"): leaf(["query", "limit"], "int", False, "page size")
    }


def test_flatten_response_paths_are_relative_to_body_root() -> None:
    op = make_op(
        "x", "GET", "/x", None, obj({"data": obj({"id": STR, "n": INT}, ["id"])})
    )
    assert flatten_response(op) == {
        ("data", "id"): leaf(["data", "id"], "str", True),
        ("data", "n"): leaf(["data", "n"], "int", False),
    }


def test_flatten_response_without_object_schema_has_no_leaves() -> None:
    assert flatten_response(make_op("x", "GET", "/x", None, None)) == {}
    assert flatten_response(make_op("x", "GET", "/x", None, {})) == {}
    arr = {"type": "array", "items": STR}
    assert flatten_response(make_op("x", "GET", "/x", None, arr)) == {}


def entry(
    change: str,
    side: str,
    path: list[str],
    type_: str,
    required: bool = True,
    **extra: str,
) -> dict:
    return {
        "change": change,
        "side": side,
        "path": path,
        "type": type_,
        "required": required,
        "description": "",
        **extra,
    }


def test_diff_identical_is_empty() -> None:
    assert diff(GET_USER, GET_USER) == []


def test_diff_field_rename_m1() -> None:
    _, new, _ = MUTATIONS["M1"]
    assert diff(GET_USER, new) == [
        entry("added", "req", ["body", "customer_id"], "str"),
        entry("removed", "req", ["body", "user_id"], "str"),
    ]


def test_diff_type_change_m2() -> None:
    _, new, _ = MUTATIONS["M2"]
    assert diff(UPDATE_EMAIL, new) == [
        entry("type_changed", "req", ["body", "user_id"], "int", old_type="str")
    ]


def test_diff_response_nesting_m3() -> None:
    _, new, _ = MUTATIONS["M3"]
    assert diff(GET_USER, new) == [
        entry("added", "resp", ["data", "email"], "str"),
        entry("added", "resp", ["data", "id"], "str"),
        entry("added", "resp", ["data", "name"], "str"),
        entry("removed", "resp", ["email"], "str"),
        entry("removed", "resp", ["id"], "str"),
        entry("removed", "resp", ["name"], "str"),
    ]


def test_diff_security_and_header_additions_m4_m5() -> None:
    _, m4, _ = MUTATIONS["M4"]
    assert diff(CREATE_TICKET, m4) == [
        entry("added", "req", ["header", "authorization"], "str")
    ]
    _, m5, _ = MUTATIONS["M5"]
    assert diff(GET_USER, m5) == [
        entry("added", "req", ["body", "target", "id"], "int"),
        entry("removed", "req", ["body", "user_id"], "str"),
        entry("added", "req", ["header", "x-tenant-id"], "str"),
    ]


def test_diff_keeps_descriptions_of_the_side_they_come_from() -> None:
    _, new, _ = MUTATIONS["M6"]
    got = diff(SET_MANAGER, new)
    by_path = {tuple(e["path"]): e for e in got}
    assert by_path[("body", "user_id")]["description"] == "ID of the user"
    assert by_path[("body", "subject")]["description"].startswith(
        "ID of the user whose"
    )


def test_diff_required_changed_and_route_changed_sort_first() -> None:
    old = make_op("x", "GET", "/v1/x", obj({"a": STR}, []), None)
    new = make_op("x", "POST", "/v2/x", obj({"a": STR}, ["a"]), None)
    assert diff(old, new) == [
        {"change": "route_changed", "side": "req", "method": "POST", "path": "/v2/x"},
        entry("required_changed", "req", ["body", "a"], "str", True),
    ]


def test_diff_orders_req_before_resp_then_by_path() -> None:
    old = make_op("x", "GET", "/x", obj({"z": STR}), obj({"a": STR}))
    new = make_op("x", "GET", "/x", obj({"b": STR}), obj({"c": STR}))
    got = [(e["side"], e["change"], e["path"]) for e in diff(old, new)]
    assert got == [
        ("req", "added", ["body", "b"]),
        ("req", "removed", ["body", "z"]),
        ("resp", "removed", ["a"]),
        ("resp", "added", ["c"]),
    ]


def test_diff_signature_ignores_descriptions_and_tracks_content() -> None:
    a = [entry("added", "req", ["body", "x"], "str", description="one")]
    b = [entry("added", "req", ["body", "x"], "str", description="other words")]
    c = [entry("added", "req", ["body", "y"], "str", description="one")]
    assert diff_signature(a) == diff_signature(b)
    assert diff_signature(a) != diff_signature(c)
    assert len(diff_signature(a)) == 64


def test_route_exists_matches_method_and_path() -> None:
    ops = {
        "get_user": {"method": "POST", "path": "/users/lookup"},
        "update_email": {"method": "PATCH", "path": "/users/email"},
    }
    assert route_exists(ops, "POST", "/users/lookup")
    assert route_exists(ops, "patch", "/users/email")
    assert not route_exists(ops, "GET", "/users/lookup")
    assert not route_exists(ops, "POST", "/v2/users/lookup")
