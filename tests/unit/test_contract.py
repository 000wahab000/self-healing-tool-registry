from __future__ import annotations

import pytest

from healer import contract
from healer.models import ErrorClass as C
from healer.models import Outcome, Side

BASE = {"body": {"user_id": "123", "email": "a@example.com"}}
USER = {"id": "123", "email": "a@example.com"}
ECHO_ID = {"type": "echo", "response": ["id"], "request": ["body", "user_id"]}


def check(data, schema=None, postchecks=(), cls=C.OK) -> Outcome:
    return contract.check(
        Outcome(cls, "rest", "200", data=data),
        output_schema=schema,
        postchecks=list(postchecks),
        base_doc=BASE,
    )


def nonempty(path):
    return {"type": "non_empty", "response": path}


@pytest.mark.parametrize(
    "data, schema, path",
    [
        ({"data": {}}, {"properties": {"data": {"required": ["id"]}}}, ["data", "id"]),
        (
            {"xs": [1, "x"]},
            {"properties": {"xs": {"items": {"type": "integer"}}}},
            ["xs", 1],
        ),
    ],
)
def test_schema_violation_path_is_the_instance_path(data, schema, path):
    out = check(data, schema)
    assert out.cls is C.E5
    assert [(v.side, v.path) for v in out.violations] == [(Side.RESP, path)]


def test_each_missing_property_is_reported_once():
    out = check({}, {"required": ["a", "b"]})
    assert [v.path for v in out.violations] == [["a"], ["b"]]


@pytest.mark.parametrize(
    "data, pc, ok",
    [
        (USER, ECHO_ID, True),
        ({"id": 123}, ECHO_ID, True),  # compared as strings
        ({"id": "9"}, ECHO_ID, False),
        ({}, ECHO_ID, False),  # response path missing
        (USER, {**ECHO_ID, "request": ["body", "nope"]}, False),  # request path missing
        ({"t": "x"}, nonempty(["t"]), True),
        ({"t": ""}, nonempty(["t"]), False),
        ({}, nonempty(["t"]), False),
    ],
)
def test_postchecks(data, pc, ok):
    out = check(data, None, [pc])
    assert (out.cls is C.OK) is ok
    if not ok:
        assert out.cls is C.E6
        assert [(v.side, v.path, v.kind) for v in out.violations] == [
            (Side.REQ, pc.get("request", []), "postcheck")
        ]


def test_schema_failure_wins_over_postcheck_and_keeps_data():
    out = check({"id": "9"}, {"required": ["email"]}, [ECHO_ID])
    assert (out.cls, out.data) == (C.E5, {"id": "9"})


def test_non_ok_outcome_is_untouched():
    out = check({}, {"required": ["id"]}, [ECHO_ID], cls=C.E2)
    assert (out.cls, out.violations) == (C.E2, [])
