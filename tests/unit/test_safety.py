from __future__ import annotations

from typing import Any

import pytest

from healer.models import ErrorClass, Reason
from healer.safety import check, jev_ok

CFG = {"TENANT_ID": "t-1"}
BASE = {
    "route": {"method": "GET", "path": "/v1/users"},
    "body": {"user_id": "123"},
    "query": {},
    "header": {},
}
MOVE = {"op": "move", "from": ["body", "user_id"], "to": ["body", "target", "id"]}
CAST = {"op": "cast", "path": ["body", "target", "id"], "to": "int"}
HEADER = {
    "op": "header",
    "name": "X-Tenant-Id",
    "src": {"ref": "config", "key": "TENANT_ID"},
}
ROUTE = {"op": "route", "method": "POST", "path": "/v2/users/lookup"}


def run(
    request_ops: list[dict], response_ops: list[dict] | None = None, **kw: Any
) -> Reason | None:
    args: dict[str, Any] = {
        "base_doc": BASE,
        "cfg": CFG,
        "cls": ErrorClass.E2,
        "tool_cfg": {},
        "n_evidence": 3,
    }
    args.update(kw)
    fix = {"request_ops": request_ops, "response_ops": response_ops or []}
    return check(fix, **args)


def test_valid_fix_passes() -> None:
    spec_paths = {("body", "target", "id")}
    spec_routes = {("POST", "/v2/users/lookup")}
    assert (
        run([MOVE, CAST, HEADER, ROUTE], spec_paths=spec_paths, spec_routes=spec_routes)
        is None
    )


def test_op_not_in_schema_is_unsafe_patch_on_either_side() -> None:
    bad = {"op": "delete", "path": ["body", "x"]}
    assert run([bad]) == Reason.UNSAFE_PATCH
    assert run([], [bad], cls=ErrorClass.E5) == Reason.UNSAFE_PATCH


def test_literal_value_op_is_unsafe_patch() -> None:
    assert run([{**MOVE, "value": "forged"}]) == Reason.UNSAFE_PATCH


def test_move_source_missing_in_base_doc_is_no_safe_value() -> None:
    missing = {"op": "move", "from": ["body", "absent"], "to": ["body", "x"]}
    assert run([missing]) == Reason.NO_SAFE_VALUE


def test_header_config_key_missing_is_no_safe_value() -> None:
    assert run([HEADER], cfg={}) == Reason.NO_SAFE_VALUE


def test_route_target_not_in_spec_is_unsafe_patch() -> None:
    assert run([ROUTE], spec_routes={("GET", "/v1/users")}) == Reason.UNSAFE_PATCH


def test_move_destination_not_in_spec_is_unsafe_patch() -> None:
    assert run([MOVE], spec_paths={("body", "other")}) == Reason.UNSAFE_PATCH


def test_cast_path_not_in_spec_is_unsafe_patch() -> None:
    cast = {"op": "cast", "path": ["body", "user_id"], "to": "int"}
    assert run([cast], spec_paths={("body", "target", "id")}) == Reason.UNSAFE_PATCH


def test_response_move_destination_not_in_spec_is_unsafe_patch() -> None:
    move = {"op": "move", "from": ["data", "id"], "to": ["id"]}
    assert (
        run([], [move], cls=ErrorClass.E5, spec_paths={("name",)})
        == Reason.UNSAFE_PATCH
    )


def test_spec_checks_skipped_when_sets_not_given() -> None:
    assert run([MOVE, ROUTE]) is None


def test_lossy_cast_is_unsafe_patch() -> None:
    base = {**BASE, "body": {"user_id": "0123"}}
    assert run([MOVE, CAST], base_doc=base) == Reason.UNSAFE_PATCH


@pytest.mark.parametrize(
    ("n_evidence", "n_ops", "expected"),
    [
        (1, 3, None),
        (1, 4, Reason.UNSAFE_PATCH),
        (0, 3, None),
        (0, 4, Reason.UNSAFE_PATCH),
        (2, 6, None),
        (2, 7, Reason.UNSAFE_PATCH),
    ],
)
def test_operation_cap(n_evidence: int, n_ops: int, expected: Reason | None) -> None:
    ops = [{"op": "route", "method": "POST", "path": "/v2/users/lookup"}] * n_ops
    assert run(ops, n_evidence=n_evidence) == expected


def test_operation_cap_counts_response_ops() -> None:
    move = {"op": "move", "from": ["data", "id"], "to": ["id"]}
    assert run([], [move] * 4, cls=ErrorClass.E5, n_evidence=1) == Reason.UNSAFE_PATCH


def test_replay_allowed_when_server_rejected() -> None:
    assert run([MOVE], cls=ErrorClass.E2) is None
    assert run([], cls=ErrorClass.E2) is None  # the "no operations" replay too


@pytest.mark.parametrize("cls", [ErrorClass.E4, ErrorClass.E6])
@pytest.mark.parametrize("request_ops", [[MOVE], []])
def test_fr_9_4_accepted_write_on_non_idempotent_tool_is_unsafe_replay(
    cls: ErrorClass, request_ops: list[dict]
) -> None:
    # E4/E6: the server accepted the request, so even replaying it unchanged may write twice
    assert run(request_ops, cls=cls) == Reason.UNSAFE_REPLAY


@pytest.mark.parametrize("cls", [ErrorClass.E4, ErrorClass.E6])
@pytest.mark.parametrize("tool_cfg", [{"idempotent": True}, {"idempotency_key": True}])
def test_replay_allowed_for_idempotent_or_keyed_tool(
    cls: ErrorClass, tool_cfg: dict
) -> None:
    assert run([MOVE], cls=cls, tool_cfg=tool_cfg) is None


def test_response_only_fix_needs_no_replay_permission() -> None:
    move = {"op": "move", "from": ["data", "id"], "to": ["id"]}
    assert run([], [move], cls=ErrorClass.E5) is None  # E5 is a local remap


def test_e5_fix_that_would_re_send_follows_the_replay_rule() -> None:
    assert run([MOVE], cls=ErrorClass.E5) == Reason.UNSAFE_REPLAY
    assert run([MOVE], cls=ErrorClass.E5, tool_cfg={"idempotent": True}) is None


@pytest.mark.parametrize(
    ("confidence", "is_write", "expected"),
    [
        (0.5, False, True),
        (0.49, False, False),
        (0.9, True, True),
        (0.89, True, False),
        (0.5, True, False),
    ],
)
def test_jev_ok_thresholds(confidence: float, is_write: bool, expected: bool) -> None:
    assert jev_ok(confidence, is_write) is expected


def test_enum_map_lossy_rejected_by_safety() -> None:
    lossy_op = {
        "op": "enum_map",
        "path": ["body", "status"],
        "mapping": {"active": "ON", "pending": "ON"},
    }
    assert (
        run([lossy_op], base_doc={"body": {"status": "active"}}) == Reason.UNSAFE_PATCH
    )


def test_enum_map_source_missing_in_base_doc_is_no_safe_value() -> None:
    op = {
        "op": "enum_map",
        "path": ["body", "missing_field"],
        "mapping": {"active": "ON"},
    }
    assert run([op], base_doc={"body": {}}) == Reason.NO_SAFE_VALUE


def test_enum_map_destination_not_in_spec_is_unsafe_patch() -> None:
    op = {
        "op": "enum_map",
        "path": ["body", "status"],
        "mapping": {"active": "ON"},
    }
    assert (
        run(
            [op],
            base_doc={"body": {"status": "active"}},
            spec_paths={("body", "other")},
        )
        == Reason.UNSAFE_PATCH
    )

