from __future__ import annotations

import copy

import pytest

from healer.models import Reason
from healer.ops import OpError, apply_ops, validate_ops

CFG = {"TENANT_ID": "t-1", "OAUTH_BEARER": "Bearer x"}


def reason_of(ops: list[dict], doc: dict, cfg: dict | None = None) -> Reason:
    with pytest.raises(OpError) as exc:
        apply_ops(ops, doc, CFG if cfg is None else cfg)
    return exc.value.reason


def cast_op(to: str) -> list[dict]:
    return [{"op": "cast", "path": ["body", "v"], "to": to}]


def test_move_rename() -> None:
    ops = [{"op": "move", "from": ["body", "user_id"], "to": ["body", "customer_id"]}]
    assert apply_ops(ops, {"body": {"user_id": "7"}}, CFG) == {
        "body": {"customer_id": "7"}
    }


def test_move_nest_creates_intermediates_and_unnest() -> None:
    nest = [{"op": "move", "from": ["body", "user_id"], "to": ["body", "target", "id"]}]
    nested = apply_ops(nest, {"body": {"user_id": "7"}}, CFG)
    assert nested == {"body": {"target": {"id": "7"}}}
    unnest = [
        {"op": "move", "from": ["body", "target", "id"], "to": ["body", "user_id"]}
    ]
    assert apply_ops(unnest, nested, CFG) == {"body": {"target": {}, "user_id": "7"}}


def test_move_on_response_body_root() -> None:
    ops = [{"op": "move", "from": ["data", "id"], "to": ["id"]}]
    assert apply_ops(ops, {"data": {"id": 1}}, CFG) == {"data": {}, "id": 1}


def test_header_sets_lowercase_name_from_config() -> None:
    ops = [
        {
            "op": "header",
            "name": "X-Tenant-Id",
            "src": {"ref": "config", "key": "TENANT_ID"},
        }
    ]
    assert apply_ops(ops, {"body": {}}, CFG) == {
        "body": {},
        "header": {"x-tenant-id": "t-1"},
    }


def test_header_missing_config_key_is_no_safe_value() -> None:
    ops = [
        {
            "op": "header",
            "name": "X-Tenant-Id",
            "src": {"ref": "config", "key": "TENANT_ID"},
        }
    ]
    assert reason_of(ops, {}, cfg={}) == Reason.NO_SAFE_VALUE


def test_route_sets_method_and_path() -> None:
    ops = [{"op": "route", "method": "POST", "path": "/v2/users/lookup"}]
    out = apply_ops(ops, {"route": {"method": "GET", "path": "/v1/users"}}, CFG)
    assert out["route"] == {"method": "POST", "path": "/v2/users/lookup"}


def test_ops_apply_in_order() -> None:
    ops = [
        {"op": "move", "from": ["body", "user_id"], "to": ["body", "target", "id"]},
        {"op": "cast", "path": ["body", "target", "id"], "to": "int"},
    ]
    assert apply_ops(ops, {"body": {"user_id": "123"}}, CFG) == {
        "body": {"target": {"id": 123}}
    }


def test_move_missing_source_is_unsafe_patch() -> None:
    ops = [{"op": "move", "from": ["body", "nope"], "to": ["body", "x"]}]
    assert reason_of(ops, {"body": {}}) == Reason.UNSAFE_PATCH


def test_cast_missing_path_is_unsafe_patch() -> None:
    assert reason_of(cast_op("int"), {"body": {}}) == Reason.UNSAFE_PATCH


def test_unknown_op_is_unsafe_patch() -> None:
    assert reason_of([{"op": "delete", "path": ["body", "x"]}], {"body": {"x": 1}}) == (
        Reason.UNSAFE_PATCH
    )


@pytest.mark.parametrize(
    "op",
    [
        {"op": "move", "from": ["body", "a"], "to": ["body", "b"], "value": "forged"},
        {
            "op": "header",
            "name": "X-A",
            "src": {"ref": "config", "key": "K"},
            "value": "v",
        },
        {"op": "header", "name": "X-A", "src": {"ref": "literal", "key": "K"}},
        {"op": "move", "from": [], "to": ["body", "b"]},
        {"op": "cast", "path": ["body", "a"], "to": "list"},
        {"op": "route", "method": "GET"},
        {"op": "enum_map", "path": ["body", "a"], "mapping": {}},
        {"op": "encoding", "content_type": ""},
        {"op": "encoding"},
    ],
)
def test_malformed_op_is_unsafe_patch(op: dict) -> None:
    assert reason_of([op], {"body": {"a": 1}}) == Reason.UNSAFE_PATCH


def test_validate_ops_accepts_valid_and_rejects_non_list() -> None:
    validate_ops([{"op": "route", "method": "GET", "path": "/x"}])
    with pytest.raises(OpError) as exc:
        validate_ops({"op": "route", "method": "GET", "path": "/x"})  # type: ignore[arg-type]
    assert exc.value.reason == Reason.UNSAFE_PATCH


@pytest.mark.parametrize(
    ("value", "to", "expected"),
    [
        ("123", "int", 123),
        (123, "int", 123),
        (3.0, "int", 3),
        (3, "float", 3.0),
        ("1.5", "float", 1.5),
        (123, "str", "123"),
        (1.5, "str", "1.5"),
        ("abc", "str", "abc"),
        ("true", "bool", True),
        ("false", "bool", False),
        (True, "bool", True),
    ],
)
def test_cast_lossless(value: object, to: str, expected: object) -> None:
    out = apply_ops(cast_op(to), {"body": {"v": value}}, CFG)["body"]["v"]
    assert out == expected
    assert type(out) is type(expected)


@pytest.mark.parametrize(
    ("value", "to"),
    [
        ("0123", "int"),
        ("12a", "int"),
        ("1.5", "int"),
        (" 12", "int"),
        (3.5, "int"),
        ("1.50", "float"),
        ("abc", "float"),
        ("yes", "bool"),
        ("True", "bool"),
        (1, "bool"),
        (None, "int"),
        ([1], "str"),
        (True, "int"),
        (True, "str"),
    ],
)
def test_cast_lossy_is_unsafe_patch(value: object, to: str) -> None:
    assert reason_of(cast_op(to), {"body": {"v": value}}) == Reason.UNSAFE_PATCH


def test_apply_ops_does_not_mutate_input() -> None:
    doc = {"body": {"user_id": "7", "nested": {"k": [1, 2]}}}
    before = copy.deepcopy(doc)
    ops = [
        {"op": "move", "from": ["body", "user_id"], "to": ["body", "target", "id"]},
        {"op": "cast", "path": ["body", "target", "id"], "to": "int"},
        {
            "op": "header",
            "name": "X-Tenant-Id",
            "src": {"ref": "config", "key": "TENANT_ID"},
        },
    ]
    out = apply_ops(ops, doc, CFG)
    assert doc == before
    assert out is not doc
    assert out["body"]["target"]["id"] == 7


def test_enum_map_bijective() -> None:
    ops = [
        {
            "op": "enum_map",
            "path": ["body", "status"],
            "mapping": {"active": "ENABLED", "inactive": "DISABLED"},
        }
    ]
    out = apply_ops(ops, {"body": {"status": "active"}}, CFG)
    assert out["body"]["status"] == "ENABLED"


def test_enum_map_lossy_rejected() -> None:
    # Non-bijective (many-to-one) mapping must be rejected with UNSAFE_PATCH
    ops = [
        {
            "op": "enum_map",
            "path": ["body", "status"],
            "mapping": {"active": "ENABLED", "pending": "ENABLED"},
        }
    ]
    assert reason_of(ops, {"body": {"status": "active"}}) == Reason.UNSAFE_PATCH

    # Value not present in bijective mapping must also be rejected
    valid_ops = [
        {
            "op": "enum_map",
            "path": ["body", "status"],
            "mapping": {"active": "ENABLED", "inactive": "DISABLED"},
        }
    ]
    assert (
        reason_of(valid_ops, {"body": {"status": "unknown"}}) == Reason.UNSAFE_PATCH
    )


def test_encoding_sets_header() -> None:
    ops = [{"op": "encoding", "content_type": "application/json"}]
    out = apply_ops(ops, {"body": {}}, CFG)
    assert out["header"]["content-type"] == "application/json"

    out_with_header = apply_ops(ops, {"header": {}}, CFG)
    assert out_with_header["header"]["content-type"] == "application/json"


def test_ac_41_enum_map_bijective_and_lossy() -> None:
    # AC-41: enum_map heals enum casing/alias; non-bijective mappings abort UNSAFE_PATCH
    bijective = [
        {
            "op": "enum_map",
            "path": ["body", "role"],
            "mapping": {"admin": "ADMIN", "member": "MEMBER"},
        }
    ]
    out = apply_ops(bijective, {"body": {"role": "admin"}}, CFG)
    assert out["body"]["role"] == "ADMIN"

    lossy = [
        {
            "op": "enum_map",
            "path": ["body", "role"],
            "mapping": {"admin": "USER", "member": "USER"},
        }
    ]
    assert reason_of(lossy, {"body": {"role": "admin"}}) == Reason.UNSAFE_PATCH


def test_ac_42_encoding_sets_content_type() -> None:
    # AC-42: encoding operation adjusts content-type
    ops = [{"op": "encoding", "content_type": "application/x-www-form-urlencoded"}]
    out = apply_ops(ops, {"body": {"a": "1"}}, CFG)
    assert out["header"]["content-type"] == "application/x-www-form-urlencoded"



