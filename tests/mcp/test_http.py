from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack, asynccontextmanager

import httpx
import pytest

pytest.importorskip("mcp")
httpx2 = pytest.importorskip("httpx2")

from mcp import ClientSession, types
from mcp.client.streamable_http import streamable_http_client

from healer.mcp_server import create_http_app

USER = {"id": "123", "name": "Ada", "email": "ada@example.com"}
URL = "http://127.0.0.1/mcp"


@pytest.fixture
def http_app(mcp_registry):
    return create_http_app(mcp_registry)


@asynccontextmanager
async def _session(stack: AsyncExitStack, client, *, notifications=None):
    async def handle_message(message):
        if notifications is not None:
            notifications.append(message)

    read_stream, write_stream = await stack.enter_async_context(
        streamable_http_client(URL, http_client=client)
    )
    session = await stack.enter_async_context(
        ClientSession(
            read_stream,
            write_stream,
            message_handler=handle_message if notifications is not None else None,
        )
    )
    await session.initialize()
    yield session


@asynccontextmanager
async def _client(app, **kwargs):
    async with app.router.lifespan_context(app), httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://127.0.0.1",
        **kwargs,
    ) as client:
        yield client


async def test_ac_35_http_list_and_healthy_call_match_registry(mcp_registry, http_app):
    async with _client(http_app) as client, AsyncExitStack() as stack:
        session = await stack.enter_async_context(_session(stack, client))
        listed = await session.list_tools()
        got = [
            {
                "name": tool["name"],
                "description": tool["description"],
                "inputSchema": tool["parameters"],
            }
            for tool in mcp_registry.tools()
        ]
        assert [
            {
                "name": t["name"],
                "description": t["description"],
                "inputSchema": t["inputSchema"],
            }
            for t in listed.model_dump(by_alias=True)["tools"]
        ] == got

        result = await session.call_tool("get_user", {"user_id": "123"})
        response = result.model_dump(by_alias=True)
        assert response["isError"] is False
        assert response["structuredContent"] == USER


async def test_ac_35_http_m1_preserves_schema_and_emits_no_list_changed(
    api, mcp_registry, http_app
):
    notices = []
    async with _client(http_app) as client, AsyncExitStack() as stack:
        session = await stack.enter_async_context(
            _session(stack, client, notifications=notices)
        )
        before = await session.list_tools()
        schema = before.model_dump(by_alias=True)["tools"]
        api.set_mutation("M1")

        result = await session.call_tool("get_user", {"user_id": "123"})

        response = result.model_dump(by_alias=True)
        assert response["isError"] is False
        assert response["structuredContent"] == USER
        assert (await session.list_tools()).model_dump(by_alias=True)["tools"] == schema
        assert not any(
            isinstance(message, types.ToolListChangedNotification)
            for message in notices
        )
        events = mcp_registry.store.audit_events()
        assert len(events) == 1
        assert events[0].outcome.value == "RECOVERED"


async def test_ac_35_http_m8_unknown_tool_and_invalid_arguments(
    api, mcp_registry, http_app
):
    async with _client(http_app) as client, AsyncExitStack() as stack:
        session = await stack.enter_async_context(_session(stack, client))
        api.set_mutation("M8")
        refusal = await session.call_tool(
            "create_ticket", {"user_id": "123", "title": "t"}
        )
        payload = refusal.model_dump(by_alias=True)
        assert payload["isError"] is True
        assert payload["structuredContent"]["reason"] == "NO_SAFE_VALUE"
        assert payload["structuredContent"]["retry"] is False
        assert "priority" not in str(payload["structuredContent"])
        assert api.state()["tickets"] == []

        unknown = await session.call_tool("not_a_tool", {})
        invalid = await session.call_tool("get_user", {"extra": True})
        assert unknown.model_dump(by_alias=True)["isError"] is True
        assert unknown.structured_content["error"] == "UNKNOWN_TOOL"
        assert invalid.model_dump(by_alias=True)["isError"] is True
        assert invalid.structured_content["error"] == "AGENT_ARG_ERROR"


async def test_ac_36_five_http_sessions_share_one_heal(
    api, mcp_registry, http_app, monkeypatch
):
    original = mcp_registry.client._transport
    failures_ready = asyncio.Event()
    followers_ready = asyncio.Event()
    failure_responses = 0
    followers = 0

    class Barrier(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            nonlocal failure_responses
            if request.url.path == "/users/lookup" and failure_responses < 5:
                response = await original.handle_async_request(request)
                failure_responses += 1
                if failure_responses == 5:
                    failures_ready.set()
                await failures_ready.wait()
                return response
            if request.url.path == "/openapi.json":
                await followers_ready.wait()
            return await original.handle_async_request(request)

    mcp_registry.client._transport = Barrier()
    original_follow = mcp_registry.healer._follow

    async def observe_follower(heal, flight):
        nonlocal followers
        followers += 1
        if followers == 4:
            followers_ready.set()
        return await original_follow(heal, flight)

    monkeypatch.setattr(mcp_registry.healer, "_follow", observe_follower)
    api.set_mutation("M1")
    async with _client(http_app) as client, AsyncExitStack() as sessions:
        clients = [await sessions.enter_async_context(_session(sessions, client)) for _ in range(5)]
        async with asyncio.timeout(10):
            results = await asyncio.gather(
                *(session.call_tool("get_user", {"user_id": "123"}) for session in clients)
            )

    assert failure_responses == 5
    assert followers == 4
    assert [result.structured_content for result in results] == [USER] * 5
    assert all(result.model_dump(by_alias=True)["isError"] is False for result in results)
    events = mcp_registry.store.audit_events()
    assert len(events) == 1
    assert events[0].outcome.value == "RECOVERED"


def _initialize_body() -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "security-test", "version": "1"},
        },
    }


async def test_ac_35_default_localhost_allows_local_host_origin_and_rejects_evil(
    http_app
):
    async with _client(http_app) as client:
        allowed = await client.post("/mcp", json=_initialize_body())
        assert allowed.status_code == 200
        host_rejected = await client.post(
            "/mcp", headers={"Host": "evil.example"}, json=_initialize_body()
        )
        origin_rejected = await client.post(
            "/mcp", headers={"Origin": "https://evil.example"}, json=_initialize_body()
        )

    assert host_rejected.status_code in (400, 421)
    assert origin_rejected.status_code in (400, 403)


async def test_ac_35_http_requires_token_for_every_method_and_valid_token_works(
    mcp_registry,
):
    token = "test-http-token"
    app = create_http_app(
        mcp_registry,
        bearer_token=token,
        allowed_hosts=["127.0.0.1:*"],
        allowed_origins=["http://127.0.0.1"],
    )
    session_id = None

    async with app.router.lifespan_context(app), httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://127.0.0.1",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        responses = []

        async def capture(response):
            if response.headers.get("Mcp-Session-Id"):
                responses.append(response.headers["Mcp-Session-Id"])

        client.event_hooks["response"].append(capture)
        async with AsyncExitStack() as stack:
            session = await stack.enter_async_context(_session(stack, client))
            result = await session.call_tool("get_user", {"user_id": "123"})
            assert result.structured_content == USER
            session_id = responses[0]
            async with httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app),
                base_url="http://127.0.0.1",
            ) as unauthenticated:
                headers = {
                    "Mcp-Session-Id": session_id,
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                }
                body = {"jsonrpc": "2.0", "id": 2, "method": "ping"}
                for method in ("POST", "GET", "DELETE"):
                    for authorization in (None, "Bearer wrong-token"):
                        request_headers = dict(headers)
                        if authorization:
                            request_headers["Authorization"] = authorization
                        response = await unauthenticated.request(
                            method,
                            "/mcp",
                            headers=request_headers,
                            json=body if method == "POST" else None,
                        )
                        assert response.status_code == 401
                        assert token not in response.text

    assert session_id


def test_ac_35_remote_http_requires_auth_and_explicit_host_policy(mcp_registry):
    with pytest.raises(ValueError):
        create_http_app(mcp_registry, host="0.0.0.0")
    with pytest.raises(ValueError):
        create_http_app(mcp_registry, host="0.0.0.0", bearer_token="token")

    app = create_http_app(
        mcp_registry,
        host="0.0.0.0",
        bearer_token="token",
        allowed_hosts=["registry.example:8443"],
        allowed_origins=["https://registry.example:8443"],
    )
    assert app is not None


async def test_ac_35_http_errors_do_not_leak_bearer_token(mcp_registry):
    token = "test-http-secret"
    app = create_http_app(
        mcp_registry,
        bearer_token=token,
        allowed_hosts=["127.0.0.1:*"],
        allowed_origins=["http://127.0.0.1"],
    )
    async with app.router.lifespan_context(app), httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://127.0.0.1"
    ) as client:
        response = await client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {token}"},
            json={"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {}},
        )
        assert response.status_code >= 400
        assert token not in response.text
        assert token not in str(response.headers)


async def test_ac_35_http_cli_defaults_and_token_environment_validation(monkeypatch):
    from healer import mcp_server

    args = mcp_server._arguments(["--transport", "http"])
    assert args.host == "127.0.0.1"
    assert args.port > 0
    assert args.allowed_host in (None, [])
    assert args.allowed_origin in (None, [])

    monkeypatch.setenv("TOKEN_ENV_TEST", "cli-secret")
    args = mcp_server._arguments(
        [
            "--transport", "http", "--token-env", "TOKEN_ENV_TEST",
            "--allowed-host", "127.0.0.1:*", "--allowed-origin", "http://127.0.0.1",
        ]
    )
    assert args.token_env == "TOKEN_ENV_TEST"
    assert "cli-secret" not in repr(args)

    class Client:
        async def aclose(self):
            pass

    class Store:
        def __init__(self, _db):
            pass

        def close(self):
            pass

    class Registry:
        def __init__(self, *_args, **_kwargs):
            pass

        async def load(self):
            pass

    monkeypatch.setattr(mcp_server.httpx, "AsyncClient", lambda **_kwargs: Client())
    monkeypatch.setattr(mcp_server, "Store", Store)
    monkeypatch.setattr(mcp_server, "Registry", Registry)
    monkeypatch.delenv("TOKEN_ENV_MISSING", raising=False)
    missing = mcp_server._arguments(
        ["--transport", "http", "--token-env", "TOKEN_ENV_MISSING"]
    )
    with pytest.raises(ValueError, match="empty"):
        await mcp_server._serve(missing)
