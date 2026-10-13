from __future__ import annotations

import pytest
from fixtures_ops import (
    CFG_KEYS,
    CREATE_TICKET_DOC,
    GET_USER_DOC,
    HEADER_SOURCES,
    MUTATIONS,
    SET_MANAGER_DOC,
    STR,
    UPDATE_EMAIL_DOC,
    doc,
    obj,
)

from healer.candidates import build, from_violations
from healer.diagnose import diff
from healer.models import Reason, Side, Violation
from healer.settings import MAX_CANDIDATES


def mutation_build(mid: str) -> tuple[list[dict], Reason | None]:
    old, new, base = MUTATIONS[mid]
    return build(diff(old, new), base, HEADER_SOURCES, CFG_KEYS)


def move(src: list[str], dst: list[str]) -> dict:
    return {"op": "move", "from": src, "to": dst}


def cast(path: list[str], to: str) -> dict:
    return {"op": "cast", "path": path, "to": to}


def header(name: str, key: str) -> dict:
    return {"op": "header", "name": name, "src": {"ref": "config", "key": key}}


def cand(request_ops: list[dict], response_ops: list[dict] | None = None) -> dict:
    return {"request_ops": request_ops, "response_ops": response_ops or []}


def e(
    change: str,
    path: list[str],
    type_: str = "str",
    required: bool = True,
    side: str = "req",
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


def run(entries: list[dict], base: dict, cfg_keys: set[str] = CFG_KEYS):
    return build(entries, base, HEADER_SOURCES, cfg_keys)


# ---- plan phase 5 table: one test per mutation ----------------------------


def test_m1_rename_is_one_move() -> None:
    assert mutation_build("M1") == (
        [cand([move(["body", "user_id"], ["body", "customer_id"])])],
        None,
    )


def test_m2_type_change_is_one_cast() -> None:
    assert mutation_build("M2") == (
        [cand([cast(["body", "user_id"], "int")])],
        None,
    )


def test_m3_response_nesting_is_three_response_moves() -> None:
    assert mutation_build("M3") == (
        [
            cand(
                [],
                [
                    move(["data", "email"], ["email"]),
                    move(["data", "id"], ["id"]),
                    move(["data", "name"], ["name"]),
                ],
            )
        ],
        None,
    )


def test_m4_bearer_security_is_header_from_config() -> None:
    assert mutation_build("M4") == (
        [cand([header("Authorization", "OAUTH_BEARER")])],
        None,
    )


def test_m5_combined_is_move_cast_header() -> None:
    assert mutation_build("M5") == (
        [
            cand(
                [
                    move(["body", "user_id"], ["body", "target", "id"]),
                    cast(["body", "target", "id"], "int"),
                    header("X-Tenant-Id", "TENANT_ID"),
                ]
            )
        ],
        None,
    )


def test_m6_ambiguous_rename_gives_both_assignments() -> None:
    cands, reason = mutation_build("M6")
    assert reason is None
    pairings = {
        tuple(
            (op["from"][-1], op["to"][-1]) for op in c["request_ops"]
        )  # (source, destination) per move
        for c in cands
    }
    assert len(cands) == 2
    assert pairings == {
        (("manager_id", "subject"), ("user_id", "supervisor")),
        (("user_id", "subject"), ("manager_id", "supervisor")),
    }


def test_m7_silent_ignore_fills_optional_field_from_removed_one() -> None:
    assert mutation_build("M7") == (
        [cand([move(["body", "email"], ["body", "email_address"])])],
        None,
    )


def test_m8_required_field_without_source_refuses() -> None:
    assert mutation_build("M8") == ([], Reason.NO_SAFE_VALUE)


@pytest.mark.parametrize("mid", sorted(MUTATIONS))
def test_same_input_twice_gives_identical_output(mid: str) -> None:
    assert mutation_build(mid) == mutation_build(mid)


# ---- FR-7.2 rules, with hand-written diff entries --------------------------


def test_name_tokens_split_camel_case_and_hyphen_and_prefer_evidence() -> None:
    entries = [
        e("removed", ["body", "note"]),
        e("removed", ["body", "userId"]),
        e("added", ["body", "memo"]),
        e("added", ["body", "user-ref"]),
    ]
    base = doc("POST", "/x", {"userId": "7", "note": "hi"})
    # user-ref shares "user" with userId, so only userId may fill it; memo has no
    # evidence and may take either, but userId is then used up.
    assert run(entries, base) == (
        [
            cand(
                [
                    move(["body", "note"], ["body", "memo"]),
                    move(["body", "userId"], ["body", "user-ref"]),
                ]
            )
        ],
        None,
    )


def test_unsafe_cast_value_drops_candidate_with_unsafe_patch() -> None:
    entries = [e("type_changed", ["body", "user_id"], "int", old_type="str")]
    base = doc("PATCH", "/x", {"user_id": "abc"})
    assert run(entries, base) == ([], Reason.UNSAFE_PATCH)


def test_type_change_for_argument_not_sent_needs_no_fix() -> None:
    entries = [e("type_changed", ["body", "limit"], "int", old_type="str")]
    assert run(entries, doc("POST", "/x", {})) == ([], Reason.NO_CANDIDATE)


def test_source_must_exist_in_base_doc() -> None:
    entries = [e("removed", ["body", "user_id"]), e("added", ["body", "customer_id"])]
    assert run(entries, doc("POST", "/x", {})) == ([], Reason.NO_SAFE_VALUE)


def test_incompatible_source_type_is_not_a_source() -> None:
    entries = [
        e("removed", ["body", "user_id"]),
        e("added", ["body", "customer_id"], "int"),
    ]
    assert run(entries, doc("POST", "/x", {"user_id": "abc"})) == (
        [],
        Reason.NO_SAFE_VALUE,
    )


def test_lossless_cast_source_gets_cast_to_target_type() -> None:
    entries = [
        e("removed", ["body", "user_id"]),
        e("added", ["body", "customer_id"], "int"),
    ]
    assert run(entries, doc("POST", "/x", {"user_id": "123"})) == (
        [
            cand(
                [
                    move(["body", "user_id"], ["body", "customer_id"]),
                    cast(["body", "customer_id"], "int"),
                ]
            )
        ],
        None,
    )


def test_one_source_cannot_fill_two_required_leaves() -> None:
    entries = [
        e("removed", ["body", "user_id"]),
        e("added", ["body", "a"]),
        e("added", ["body", "b"]),
    ]
    assert run(entries, doc("POST", "/x", {"user_id": "1"})) == (
        [],
        Reason.NO_SAFE_VALUE,
    )


def test_optional_leaf_is_filled_only_by_unconsumed_evidence_source() -> None:
    entries = [
        e("removed", ["body", "email"]),
        e("added", ["body", "backup_email"], required=False),
        e("added", ["body", "email_address"]),
    ]
    base = doc("POST", "/x", {"email": "a@b.c"})
    assert run(entries, base) == (
        [cand([move(["body", "email"], ["body", "email_address"])])],
        None,
    )


def test_optional_leaf_without_name_evidence_is_left_alone() -> None:
    entries = [
        e("removed", ["body", "alpha"]),
        e("removed", ["body", "beta"]),
        e("added", ["body", "gamma"], required=False),
    ]
    base = doc("POST", "/x", {"alpha": "1", "beta": "2"})
    assert run(entries, base) == ([], Reason.NO_CANDIDATE)


def test_optional_leaf_with_two_evidence_sources_gives_two_candidates() -> None:
    entries = [
        e("removed", ["body", "home_email"]),
        e("removed", ["body", "work_email"]),
        e("added", ["body", "email_address"], required=False),
    ]
    base = doc("POST", "/x", {"home_email": "h@x.y", "work_email": "w@x.y"})
    assert run(entries, base) == (
        [
            cand([move(["body", "home_email"], ["body", "email_address"])]),
            cand([move(["body", "work_email"], ["body", "email_address"])]),
        ],
        None,
    )


def test_candidates_are_capped() -> None:
    names = ["alpha", "beta", "gamma", "delta"]
    news = ["one", "two", "three", "four"]
    entries = [e("removed", ["body", n]) for n in names] + [
        e("added", ["body", n]) for n in news
    ]
    base = doc("POST", "/x", {n: n for n in names})
    cands, reason = run(entries, base)
    assert reason is None
    assert len(cands) == MAX_CANDIDATES
    assert len({repr(c) for c in cands}) == MAX_CANDIDATES


def test_added_required_header_needs_a_mapped_config_key() -> None:
    entries = [e("added", ["header", "x-tenant-id"])]
    base = doc("POST", "/x", {})
    assert run(entries, base) == (
        [cand([header("X-Tenant-Id", "TENANT_ID")])],
        None,
    )
    assert run(entries, base, cfg_keys={"OAUTH_BEARER"}) == ([], Reason.NO_SAFE_VALUE)
    unmapped = [e("added", ["header", "x-api-key"])]
    assert run(unmapped, base) == ([], Reason.NO_SAFE_VALUE)


def test_added_optional_header_needs_nothing() -> None:
    entries = [e("added", ["header", "x-trace"], required=False)]
    assert run(entries, doc("POST", "/x", {})) == ([], Reason.NO_CANDIDATE)


def test_route_change_becomes_route_op() -> None:
    entries = [
        {"change": "route_changed", "side": "req", "method": "POST", "path": "/v2/x"}
    ]
    assert run(entries, doc("GET", "/x", {})) == (
        [cand([{"op": "route", "method": "POST", "path": "/v2/x"}])],
        None,
    )


def test_no_entries_means_no_candidate() -> None:
    assert run([], GET_USER_DOC) == ([], Reason.NO_CANDIDATE)


def test_removed_field_alone_needs_no_fix() -> None:
    assert run([e("removed", ["body", "user_id"])], GET_USER_DOC) == (
        [],
        Reason.NO_CANDIDATE,
    )


def test_response_leaf_with_changed_type_is_moved_then_cast_back() -> None:
    entries = [
        e("removed", ["id"], "str", side="resp"),
        e("added", ["data", "id"], "int", side="resp"),
    ]
    assert run(entries, GET_USER_DOC) == (
        [cand([], [move(["data", "id"], ["id"]), cast(["id"], "str")])],
        None,
    )


def test_ambiguous_response_relocation_is_not_guessed() -> None:
    entries = [
        e("removed", ["id"], side="resp"),
        e("added", ["a", "id"], side="resp"),
        e("added", ["b", "id"], side="resp"),
    ]
    assert run(entries, GET_USER_DOC) == ([], Reason.NO_CANDIDATE)


def test_response_type_change_at_same_path_is_cast_back() -> None:
    entries = [e("type_changed", ["id"], "int", side="resp", old_type="str")]
    assert run(entries, GET_USER_DOC) == (
        [cand([], [cast(["id"], "str")])],
        None,
    )


def test_input_is_not_mutated_and_ops_do_not_alias_entries() -> None:
    old, new, base = MUTATIONS["M1"]
    entries = diff(old, new)
    snapshot = [dict(x, path=list(x["path"])) for x in entries]
    cands, _ = build(entries, base, HEADER_SOURCES, CFG_KEYS)
    cands[0]["request_ops"][0]["to"].append("zzz")
    assert entries == snapshot


# ---- error-clue mode (C7b) -------------------------------------------------


def v(side: Side, path: list[str], kind: str) -> Violation:
    return Violation(side, path, kind)


def test_clue_m1_missing_field_filled_from_name_matching_argument() -> None:
    got = from_violations(
        [v(Side.REQ, ["body", "customer_id"], "missing")],
        GET_USER_DOC,
        HEADER_SOURCES,
        CFG_KEYS,
    )
    assert got == (
        [cand([move(["body", "user_id"], ["body", "customer_id"])])],
        None,
    )


def test_clue_m2_type_error_becomes_cast() -> None:
    got = from_violations(
        [v(Side.REQ, ["body", "user_id"], "int_type")],
        UPDATE_EMAIL_DOC,
        HEADER_SOURCES,
        CFG_KEYS,
    )
    assert got == ([cand([cast(["body", "user_id"], "int")])], None)


def test_clue_m5_combined_change_aborts_with_no_candidate() -> None:
    got = from_violations(
        [
            v(Side.REQ, ["body", "target"], "missing"),
            v(Side.REQ, ["header", "x-tenant-id"], "missing"),
        ],
        GET_USER_DOC,
        HEADER_SOURCES,
        CFG_KEYS,
    )
    assert got == ([], Reason.NO_CANDIDATE)


def test_clue_m4_auth_violation_becomes_header() -> None:
    violations = [v(Side.REQ, ["header", "authorization"], "auth")]
    assert from_violations(violations, CREATE_TICKET_DOC, HEADER_SOURCES, CFG_KEYS) == (
        [cand([header("Authorization", "OAUTH_BEARER")])],
        None,
    )
    assert from_violations(violations, CREATE_TICKET_DOC, HEADER_SOURCES, set()) == (
        [],
        Reason.NO_SAFE_VALUE,
    )


def test_clue_m8_missing_field_without_any_source_refuses() -> None:
    got = from_violations(
        [v(Side.REQ, ["body", "priority"], "missing")],
        CREATE_TICKET_DOC,
        HEADER_SOURCES,
        CFG_KEYS,
    )
    assert got == ([], Reason.NO_SAFE_VALUE)


def test_clue_only_argument_fills_the_only_missing_field() -> None:
    got = from_violations(
        [v(Side.REQ, ["body", "mail"], "missing")],
        doc("PATCH", "/x", {"email": "a@b.c"}),
        HEADER_SOURCES,
        CFG_KEYS,
    )
    assert got == ([cand([move(["body", "email"], ["body", "mail"])])], None)


def test_clue_ambiguous_names_give_one_candidate_per_assignment() -> None:
    got = from_violations(
        [
            v(Side.REQ, ["body", "customer_id"], "missing"),
            v(Side.REQ, ["body", "owner_id"], "missing"),
        ],
        SET_MANAGER_DOC,
        HEADER_SOURCES,
        CFG_KEYS,
    )
    cands, reason = got
    assert reason is None
    assert len(cands) == 2


def test_clue_unsafe_cast_is_unsafe_patch() -> None:
    got = from_violations(
        [v(Side.REQ, ["body", "user_id"], "int_type")],
        doc("PATCH", "/x", {"user_id": "abc"}),
        HEADER_SOURCES,
        CFG_KEYS,
    )
    assert got == ([], Reason.UNSAFE_PATCH)


@pytest.mark.parametrize(
    "violations",
    [
        [],
        [v(Side.REQ, ["route"], "route")],
        [v(Side.REQ, [], "rejected")],
        [v(Side.REQ, ["header"], "auth")],
        [v(Side.REQ, ["body", "email"], "postcheck")],
        [v(Side.REQ, ["body", "limit"], "int_type")],  # argument was never sent
    ],
)
def test_clue_mode_without_enough_evidence_is_no_candidate(
    violations: list[Violation],
) -> None:
    got = from_violations(violations, GET_USER_DOC, HEADER_SOURCES, CFG_KEYS)
    assert got == ([], Reason.NO_CANDIDATE)


RESP_DATA = {"data": {"id": "123", "name": "Ada", "email": "ada@example.com"}}


def test_clue_response_missing_fields_are_located_in_body() -> None:
    got = from_violations(
        [v(Side.RESP, [k], "missing") for k in ("id", "name", "email")],
        GET_USER_DOC,
        HEADER_SOURCES,
        CFG_KEYS,
        response_data=RESP_DATA,
        expected_schema=obj({"id": STR, "name": STR, "email": STR}),
    )
    assert got == (
        [
            cand(
                [],
                [
                    move(["data", "id"], ["id"]),
                    move(["data", "name"], ["name"]),
                    move(["data", "email"], ["email"]),
                ],
            )
        ],
        None,
    )


def test_clue_response_moved_value_is_cast_to_expected_type() -> None:
    got = from_violations(
        [v(Side.RESP, ["id"], "missing")],
        GET_USER_DOC,
        HEADER_SOURCES,
        CFG_KEYS,
        response_data=RESP_DATA,
        expected_schema=obj({"id": {"type": "integer"}}),
    )
    assert got == (
        [cand([], [move(["data", "id"], ["id"]), cast(["id"], "int")])],
        None,
    )


def test_clue_response_type_violation_is_cast_to_expected_type() -> None:
    got = from_violations(
        [v(Side.RESP, ["id"], "type")],
        GET_USER_DOC,
        HEADER_SOURCES,
        CFG_KEYS,
        response_data={"id": 123},
        expected_schema=obj({"id": STR}),
    )
    assert got == ([cand([], [cast(["id"], "str")])], None)


@pytest.mark.parametrize(
    ("data", "schema"),
    [
        (None, None),  # no body to look in
        ({"a": {"id": "1"}, "b": {"id": "2"}}, None),  # ambiguous location
        ({"x": 1}, None),  # nowhere to be found
    ],
)
def test_clue_response_without_unique_location_is_no_candidate(
    data: dict | None, schema: dict | None
) -> None:
    got = from_violations(
        [v(Side.RESP, ["id"], "missing")],
        GET_USER_DOC,
        HEADER_SOURCES,
        CFG_KEYS,
        response_data=data,
        expected_schema=schema,
    )
    assert got == ([], Reason.NO_CANDIDATE)


def test_clue_mixed_request_and_response_violations_abort() -> None:
    got = from_violations(
        [v(Side.REQ, ["body", "user_id"], "int_type"), v(Side.RESP, ["id"], "missing")],
        GET_USER_DOC,
        HEADER_SOURCES,
        CFG_KEYS,
        response_data=RESP_DATA,
    )
    assert got == ([], Reason.NO_CANDIDATE)
