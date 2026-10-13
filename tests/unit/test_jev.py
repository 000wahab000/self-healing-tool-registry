from __future__ import annotations

import json

import httpx
import pytest

from healer import candidates, diagnose
from healer.jev import JevChoice, JevClient, JevUnavailable, render_option, render_state
from healer.settings import JEV_TIMEOUT_S

URL = "https://api.typesafe.ai/v1/systemone"
OPTIONS = ["move body.user_id -> body.subject", "move body.user_id -> body.supervisor"]


def reply(choice="A", confidence=0.9, usage=None) -> dict:
    out = {
        "model": "jev-latest",
        "answers": {
            "fix": {
                "type": "choice",
                "choice": choice,
                "probabilities": {"A": 0.9, "B": 0.1},
                "confidence": confidence,
            }
        },
    }
    if usage is not None:
        out["usage"] = usage
    return out


@pytest.fixture
async def jev():
    async with httpx.AsyncClient() as http:
        yield JevClient("sk-test", client=http)


async def test_request_matches_wire_contract(respx_mock, jev):
    route = respx_mock.post(URL).respond(json=reply())
    await jev.choose("STATE", "Which fix?", OPTIONS)
    request = route.calls.last.request
    assert json.loads(request.content) == {
        "model": "jev-latest",
        "state": "STATE",
        "questions": {
            "fix": {
                "type": "choice",
                "instructions": "Which fix?",
                "criteria": {"A": OPTIONS[0], "B": OPTIONS[1]},
            }
        },
    }
    assert request.headers["authorization"] == "Bearer sk-test"
    assert request.headers["content-type"].startswith("application/json")
    assert route.call_count == 1


async def test_model_and_url_are_constructor_arguments(respx_mock):
    route = respx_mock.post("https://gw.example/v1/jev").respond(json=reply())
    async with httpx.AsyncClient() as http:
        gateway = JevClient(
            "k", client=http, model="jev-x", url="https://gw.example/v1/jev"
        )
        await gateway.choose("s", "q", OPTIONS)
    assert json.loads(route.calls.last.request.content)["model"] == "jev-x"


async def test_request_uses_the_jev_timeout(respx_mock, jev):
    route = respx_mock.post(URL).respond(json=reply())
    await jev.choose("s", "q", OPTIONS)
    timeout = route.calls.last.request.extensions["timeout"]
    assert set(timeout.values()) == {JEV_TIMEOUT_S}


@pytest.mark.parametrize(("label", "index"), [("A", 0), ("B", 1), ("C", 2)])
async def test_label_maps_back_to_option_index(respx_mock, jev, label, index):
    respx_mock.post(URL).respond(json=reply(choice=label))
    choice = await jev.choose("s", "q", ["x", "y", "z"])
    assert choice.index == index


async def test_confidence_and_tokens_are_parsed(respx_mock, jev):
    usage = {"input_tokens": 312, "output_tokens": 48}
    respx_mock.post(URL).respond(json=reply("B", 0.93, usage))
    assert await jev.choose("s", "q", OPTIONS) == JevChoice(1, 0.93, 360)


async def test_tokens_are_zero_without_usage(respx_mock, jev):
    respx_mock.post(URL).respond(json=reply())
    assert (await jev.choose("s", "q", OPTIONS)).tokens == 0


@pytest.mark.parametrize("exc", [httpx.TimeoutException, httpx.ConnectError])
async def test_transport_error_is_unavailable_and_not_retried(respx_mock, jev, exc):
    route = respx_mock.post(URL).mock(side_effect=exc)
    with pytest.raises(JevUnavailable):
        await jev.choose("s", "q", OPTIONS)
    assert route.call_count == 1


NAN = '{"answers": {"fix": {"choice": "A", "confidence": NaN}}}'
BAD_REPLIES = [
    (500, ""),
    (401, '{"error": "bad key"}'),
    (429, ""),
    (302, ""),
    (200, "not json"),
    (200, "null"),
    (200, "[]"),
    (200, "{}"),
    (200, '{"answers": {}}'),
    (200, '{"answers": {"fix": {"type": "choice", "confidence": 0.9}}}'),
    (200, '{"answers": {"fix": {"choice": null, "confidence": 0.9}}}'),
    (200, '{"answers": {"fix": {"choice": "Z", "confidence": 0.9}}}'),
    (200, '{"answers": {"fix": {"choice": "C", "confidence": 0.9}}}'),  # only A, B sent
    (200, '{"answers": {"fix": {"choice": "A"}}}'),
    (200, '{"answers": {"fix": {"choice": "A", "confidence": 1.5}}}'),
    (200, NAN),
]


@pytest.mark.parametrize(("status", "content"), BAD_REPLIES)
async def test_bad_reply_is_unavailable_and_not_retried(
    respx_mock, jev, status, content
):
    route = respx_mock.post(URL).respond(status_code=status, content=content)
    with pytest.raises(JevUnavailable):
        await jev.choose("s", "q", OPTIONS)
    assert route.call_count == 1


async def test_owned_client_works_and_a_passed_client_stays_open(respx_mock):
    respx_mock.post(URL).respond(json=reply())
    owner = JevClient("k")
    assert (await owner.choose("s", "q", OPTIONS)).index == 0
    await owner.aclose()
    async with httpx.AsyncClient() as http:
        borrower = JevClient("k", client=http)
        await borrower.aclose()
        assert not http.is_closed


ENTRIES = [
    {
        "change": "removed",
        "side": "req",
        "path": ["body", "user_id"],
        "type": "str",
        "required": True,
        "description": "ID of the user",
    },
    {
        "change": "added",
        "side": "req",
        "path": ["body", "subject"],
        "type": "str",
        "required": True,
        "description": "ID of the user whose manager is being set",
    },
    {
        "change": "type_changed",
        "side": "resp",
        "path": ["age"],
        "type": "int",
        "required": False,
        "description": "",
        "old_type": "str",
    },
    {"change": "route_changed", "side": "req", "method": "POST", "path": "/v2/manager"},
]
BASE_DOC = {
    "route": {"method": "POST", "path": "/users/manager"},
    "body": {
        "user_id": "123",
        "manager_id": "456",
        "meta": {"n": 5, "mail": "ada@example.com"},
    },
    "query": {"verbose": True},
    "header": {"authorization": "Bearer secret-token"},
}


def test_render_state_has_the_diff_and_argument_types():
    text = render_state(ENTRIES, BASE_DOC)
    for fragment in (
        "body.user_id",
        "body.subject",
        "ID of the user whose manager is being set",
        "int",
        "/v2/manager",
        "body.manager_id: str",
        "body.meta.n: int",
        "body.meta.mail: str",
        "query.verbose: bool",
    ):
        assert fragment in text


def test_render_state_never_contains_argument_values():
    text = render_state(ENTRIES, BASE_DOC)
    for value in ("123", "456", "ada@example.com", "secret-token"):
        assert value not in text


def test_render_state_is_deterministic():
    reordered = {
        **BASE_DOC,
        "body": {
            "meta": {"mail": "ada@example.com", "n": 5},
            "manager_id": "456",
            "user_id": "123",
        },
    }
    assert render_state(ENTRIES, BASE_DOC) == render_state(ENTRIES, BASE_DOC)
    assert render_state(ENTRIES, BASE_DOC) == render_state(ENTRIES, reordered)


CANDIDATE = {
    "request_ops": [
        {"op": "move", "from": ["body", "user_id"], "to": ["body", "subject"]},
        {"op": "cast", "path": ["body", "age"], "to": "int"},
        {
            "op": "header",
            "name": "X-Tenant-Id",
            "src": {"ref": "config", "key": "TENANT_ID"},
        },
        {"op": "route", "method": "POST", "path": "/v2/manager"},
    ],
    "response_ops": [{"op": "move", "from": ["data", "id"], "to": ["id"]}],
}


def test_render_option_lists_every_op():
    text = render_option(CANDIDATE)
    for fragment in (
        "move body.user_id -> body.subject",
        "cast body.age to int",
        "X-Tenant-Id",
        "TENANT_ID",
        "POST /v2/manager",
        "move data.id -> id",
    ):
        assert fragment in text
    assert text == render_option(CANDIDATE)


def _set_manager_op(props: dict[str, str]) -> dict:
    return {
        "operation_id": "set_manager",
        "method": "POST",
        "path": "/users/manager",
        "body_schema": {
            "type": "object",
            "required": list(props),
            "properties": {
                k: {"type": "string", "description": d} for k, d in props.items()
            },
        },
        "params": [],
        "security": [],
        "response_schema": None,
        "description": "",
    }


async def test_real_diff_and_candidates_render_and_round_trip(respx_mock, jev):
    old = _set_manager_op(
        {"user_id": "ID of the user", "manager_id": "ID of the manager"}
    )
    new = _set_manager_op(
        {
            "subject": "ID of the user whose manager is being set",
            "supervisor": "User ID of the new manager",
        }
    )
    base_doc = {
        "route": {"method": "POST", "path": "/users/manager"},
        "body": {"user_id": "123", "manager_id": "456"},
        "query": {},
        "header": {},
    }
    entries = diagnose.diff(old, new)
    cands, reason = candidates.build(entries, base_doc, {}, set())
    assert reason is None
    assert len(cands) == 2

    state = render_state(entries, base_doc)
    assert "ID of the user whose manager is being set" in state
    assert "User ID of the new manager" in state
    assert "123" not in state
    assert "456" not in state

    options = [render_option(c) for c in cands]
    assert len(set(options)) == 2
    for text in options:
        assert text.count("move") == 2

    respx_mock.post(URL).respond(json=reply("B", 0.95))
    picked = await jev.choose(state, "Which fix?", options)
    assert picked.index == 1


def test_from_env_prefers_direct_key_then_openrouter_then_none():
    from healer.jev import from_env

    direct = from_env(
        {
            "JEV_API_KEY": "k",
            "JEV_URL": "https://x/v1/systemone",
            "OPENROUTER_API_KEY": "o",
        }
    )
    assert (direct._url, direct._model) == ("https://x/v1/systemone", "jev-latest")
    routed = from_env({"OPENROUTER_API_KEY": "o"})
    assert (routed._url, routed._model) == (
        "https://openrouter.ai/api/v1/systemone",
        "~typesafe/jev-latest",
    )
    assert from_env({}) is None
