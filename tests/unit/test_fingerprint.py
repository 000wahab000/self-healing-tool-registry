from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

import pytest

from healer.fingerprint import fingerprint
from healer.models import ErrorClass, Outcome, Side, Violation


def outcome(
    cls: ErrorClass = ErrorClass.E2,
    violations: list[Violation] | None = None,
    data: object = None,
    raw_code: str = "422",
) -> Outcome:
    if violations is None:
        violations = [
            Violation(Side.REQ, ["body", "target"], "missing"),
            Violation(Side.REQ, ["header", "x-tenant-id"], "missing"),
        ]
    return Outcome(cls, "rest", raw_code, data=data, violations=violations)


def test_ac_04_fingerprint_stable():
    first = fingerprint("get_user", outcome())
    second = fingerprint("get_user", outcome())
    assert first == second
    fp, _ = first
    assert len(fp) == 16
    int(fp, 16)

    # ids and other values in `data` are volatile and must not matter
    assert fingerprint("get_user", outcome(data={"id": "123"})) == first
    assert fingerprint("get_user", outcome(data={"id": "999", "ts": 1})) == first

    # violation order and duplicates do not matter
    a, b = outcome().violations
    assert fingerprint("get_user", outcome(violations=[b, a, b])) == first

    # a different tool or break is a different fingerprint
    assert fingerprint("update_email", outcome())[0] != fp
    assert fingerprint("get_user", outcome(raw_code="404"))[0] != fp
    assert fingerprint("get_user", outcome(violations=[a]))[0] != fp


def test_int_path_elements_are_normalised():
    one = outcome(
        cls=ErrorClass.E5,
        violations=[Violation(Side.RESP, ["items", 0, "id"], "missing")],
    )
    other = outcome(
        cls=ErrorClass.E5,
        violations=[Violation(Side.RESP, ["items", 7, "id"], "missing")],
    )
    fp, sig = fingerprint("list_things", one)
    assert fingerprint("list_things", other) == (fp, sig)
    assert sig["v"] == [["resp", ["items", "[]", "id"], "missing"]]


def test_signature_matches_documented_format():
    _, sig = fingerprint(
        "get_user",
        outcome(violations=[Violation(Side.REQ, ["header", "x-tenant-id"], "missing")]),
    )
    expected = {
        "tool": "get_user",
        "proto": "rest",
        "class": "E2",
        "code": "422",
        "v": [["req", ["header", "x-tenant-id"], "missing"]],
    }
    assert sig == expected
    # hashed independently of canonical.py: sorted keys, no whitespace
    blob = json.dumps(expected, sort_keys=True, separators=(",", ":"))
    want = hashlib.sha256(blob.encode()).hexdigest()[:16]
    assert (
        fingerprint(
            "get_user",
            outcome(
                violations=[Violation(Side.REQ, ["header", "x-tenant-id"], "missing")]
            ),
        )[0]
        == want
    )


def test_diff_signature_only_counts_for_e6():
    e6 = outcome(
        cls=ErrorClass.E6,
        violations=[Violation(Side.REQ, ["body", "user_id"], "postcheck")],
        raw_code="200",
    )
    fp_a, sig_a = fingerprint("update_email", e6, "diff-aaa")
    fp_b, _ = fingerprint("update_email", e6, "diff-bbb")
    assert fp_a != fp_b
    assert sig_a["diff"] == "diff-aaa"

    for cls in (ErrorClass.E2, ErrorClass.E5, ErrorClass.E3):
        o = outcome(cls=cls)
        fp1, sig1 = fingerprint("get_user", o, "diff-aaa")
        fp2, _ = fingerprint("get_user", o, "diff-bbb")
        assert fp1 == fp2 == fingerprint("get_user", o)[0]
        assert "diff" not in sig1


@pytest.mark.parametrize("seed", ["1", "2"])
def test_fingerprint_stable_across_processes(seed):
    """A fresh interpreter (different str hash seed) gets the same fingerprint."""
    code = (
        "from healer.fingerprint import fingerprint\n"
        "from healer.models import ErrorClass, Outcome, Side, Violation\n"
        "o = Outcome(ErrorClass.E2, 'rest', '422', violations=["
        "Violation(Side.REQ, ['body', 'target'], 'missing'),"
        "Violation(Side.REQ, ['header', 'x-tenant-id'], 'missing'),"
        "Violation(Side.REQ, ['body', 'items', 3, 'id'], 'type')])\n"
        "print(fingerprint('get_user', o)[0])\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        env={**os.environ, "PYTHONHASHSEED": seed},
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    here = fingerprint(
        "get_user",
        outcome(
            violations=[
                Violation(Side.REQ, ["body", "target"], "missing"),
                Violation(Side.REQ, ["header", "x-tenant-id"], "missing"),
                Violation(Side.REQ, ["body", "items", 3, "id"], "type"),
            ]
        ),
    )[0]
    assert out == here
