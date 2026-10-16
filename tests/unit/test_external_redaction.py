from __future__ import annotations

import base64
import json

import pytest

from healer.heal import Healer
from healer.models import ErrorClass, LoadedSpec, Outcome
from healer.repair import render
from healer.spec_watcher import SpecWatcher
from healer.store import REDACTED, redact_value, sanitize
from healer.verify import Verifier


def test_ac_91_raw_and_derived_credentials_are_redacted() -> None:
    bearer = "unit-secret-token"
    basic = base64.b64encode(b"unit-user:unit-password").decode()
    text = (
        f"token={bearer}; Authorization: Bearer {bearer}; "
        f'"authorization": "Basic {basic}"'
    )

    redacted = sanitize(text, [bearer, f"Bearer {bearer}", f"Basic {basic}"])

    assert bearer not in redacted
    assert basic not in redacted
    assert redacted.count(REDACTED) >= 2


def test_ac_91_escaped_and_unprefixed_basic_secrets_stay_valid_json() -> None:
    secret = 'quote"\\line\n雪'
    basic = base64.b64encode(b"raw-user:raw-password").decode()
    source = {"echo": secret, "basic": basic, "schema": {"description": "x" * 5000}}

    safe = redact_value(source, [secret, f"Basic {basic}"])
    encoded_safe = sanitize(
        json.dumps(source),
        [secret, f"Basic {basic}"],
        max_chars=None,
    )

    assert safe["echo"] == REDACTED
    assert safe["basic"] == REDACTED
    assert sanitize("raw-user raw-password", [f"Basic {basic}"]) == f"{REDACTED} {REDACTED}"
    assert sanitize("plain", ["Basic "]) == "plain"
    assert len(safe["schema"]["description"]) == 5000
    assert json.loads(encoded_safe)["echo"] == REDACTED
    assert json.loads(encoded_safe)["basic"] == REDACTED


def test_ac_91_repair_prompt_redacts_error_and_spec_echoes() -> None:
    secret = "prompt-secret-token"
    op = {
        "method": "GET", "path": "/records", "description": secret,
        "params": [], "security": [],
        "body_schema": {"type": "object", "properties": {}},
    }
    prompt = render(
        "records", op, {"records": op},
        Outcome(ErrorClass.E2, "rest", "401", {"error": secret}),
        {"body": {}, "query": {}, "route": {"method": "GET", "path": "/records"}},
        set(), [secret],
    )

    assert secret not in prompt
    assert REDACTED in prompt


def test_ac_91_repair_prompt_is_not_truncated_by_redactor() -> None:
    op = {
        "method": "GET", "path": "/records", "description": "",
        "params": [
            {
                "in": "query", "name": f"field_{i}", "required": False,
                "schema": {"type": "string", "enum": [f"value_{i}_" + "x" * 150]},
                "description": "",
            }
            for i in range(20)
        ],
        "security": [], "body_schema": None,
    }
    prompt = render(
        "records", op, {"records": op}, Outcome(ErrorClass.E2, "rest", "400"),
        {"body": {}, "query": {}, "route": {"method": "GET", "path": "/records"}},
        set(),
    )

    assert len(prompt) > 2048
    assert prompt.endswith("CONFIG KEYS: []")


def test_ac_91_agent_facing_api_error_redacts_credentials() -> None:
    token = "response-secret-token"
    auth = f"Bearer {token}"
    healer = object.__new__(Healer)
    healer._secrets = (auth, token)
    result = healer._safe_api_error(
        Outcome(ErrorClass.BUSINESS, "rest", "401", {"echo": auth, "token": token})
    )

    assert token not in str(result)
    assert REDACTED in str(result)


@pytest.mark.parametrize(
    ("configured", "status"), [("approved", "pass"), ("wrong", "fail")]
)
def test_ac_88_l2_validates_effective_config_header(configured, status) -> None:
    healer = object.__new__(Healer)
    healer._cfg = {"X-Mode": configured}
    healer._header_sources = {"X-Mode": "X-Mode"}
    base = {
        "route": {"method": "GET", "path": "/records"},
        "body": {}, "query": {},
        "header": {"x-mode": {"ref": "config", "key": "X-Mode"}},
    }
    spec = {
        "method": "GET", "path": "/records", "body_schema": None,
        "params": [{"in": "header", "name": "X-Mode", "required": True,
                    "schema": {"type": "string", "enum": ["approved"]}}],
        "security": [], "response_schema": None,
    }

    validation_doc = healer._validation_doc(base)
    layers = Verifier().preflight(
        base_doc=validation_doc,
        current_spec=spec,
        fix={"request_ops": [], "response_ops": []},
        original_failure=ErrorClass.E2,
        cfg=healer._cfg,
        tool_cfg={"idempotent": True},
        original_status="401",
    )

    assert base["header"]["x-mode"]["ref"] == "config"
    assert validation_doc["header"]["x-mode"] == configured
    assert layers[1]["status"] == status


def test_ac_88_l2_checks_path_params_and_accepts_move_to_renamed_param() -> None:
    base = {
        "route": {"method": "GET", "path": "/records/{old}"},
        "route_params": {"old": "existing-value"},
        "body": {}, "query": {}, "header": {},
    }
    spec = {
        "method": "GET", "path": "/records/{new}", "body_schema": None,
        "params": [{"in": "path", "name": "new", "required": True,
                    "schema": {"type": "string"}}],
        "security": [], "response_schema": None,
    }
    layers = Verifier().preflight(
        base_doc=base,
        current_spec=spec,
        fix={
            "request_ops": [
                {"op": "route", "method": "GET", "path": "/records/{new}"},
                {"op": "move", "from": ["route_params", "old"],
                 "to": ["route_params", "new"]},
            ],
            "response_ops": [],
        },
        original_failure=ErrorClass.E2,
        cfg={},
        tool_cfg={"idempotent": True},
        original_status="404",
    )

    assert layers[1]["status"] == "pass"


async def test_ac_91_watcher_redacts_snapshot_without_mutating_loaded_spec(tmp_path) -> None:
    from healer.store import Store

    secret = "watcher-private-token"
    spec = LoadedSpec(
        {"description": "x" * 5000, "token": secret}, {}, "spec-hash"
    )

    async def source() -> LoadedSpec:
        return spec

    healer = object.__new__(Healer)
    healer._secrets = (secret,)

    store = Store(str(tmp_path / "watcher.db"))
    try:
        await SpecWatcher({"api": source}, store=store, healer=healer).poll()
        saved = store.get_spec("spec-hash")
        assert saved["token"] == REDACTED
        assert len(saved["description"]) == 5000
        assert spec.raw["token"] == secret
    finally:
        store.close()
