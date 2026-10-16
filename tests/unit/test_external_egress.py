from __future__ import annotations

import httpx
import pytest

from healer.connection_security import PinnedAsyncTransport, check_egress


def test_ac_106_credential_targets_require_tls_and_exact_origin() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        check_egress("http://example.com", credentials=True, env={})
    check_egress(
        "http://localhost:8000",
        credentials=True,
        mock_transport=True,
        env={"CONNECTIONS_ALLOWED_ORIGINS": "http://localhost:8000"},
    )


def test_ac_106_reject_private_and_malformed_destinations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="unsafe connection"):
        check_egress("file:///etc/passwd", env={})


@pytest.mark.asyncio
async def test_ac_106_public_dns_uses_pinned_transport_without_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "healer.connection_security.socket.getaddrinfo",
        lambda *a, **k: [(None, None, None, None, ("93.184.216.34", 443))],
    )
    transport = PinnedAsyncTransport(
        "https://example.com",
        env={},
        inner=httpx.MockTransport(lambda request: httpx.Response(200)),
    )
    await transport.handle_async_request(httpx.Request("GET", "https://example.com/"))
    await transport.aclose()


def test_ac_111_redirect_clients_are_disabled() -> None:
    from healer.connection_security import no_redirect_client, no_redirect_httpx2

    client = no_redirect_client()
    try:
        assert client.follow_redirects is False
    finally:
        import asyncio

        asyncio.run(client.aclose())
    client2 = no_redirect_httpx2("https://mcp.example/mcp", {})
    try:
        assert client2.follow_redirects is False
        assert client2.trust_env is False
    finally:
        import asyncio

        asyncio.run(client2.aclose())


@pytest.mark.asyncio
async def test_ac_106_model_route_cannot_escape_connection_origin() -> None:
    from healer.connection_security import no_redirect_client

    async with no_redirect_client(
        base_url="https://api.example.com",
        transport=httpx.MockTransport(lambda request: httpx.Response(200)),
    ) as client:
        with pytest.raises(ValueError, match="outside connection origin"):
            await client.get("https://evil.example/path")


@pytest.mark.asyncio
async def test_ac_106_dns_is_resolved_once_and_dial_pins_host_and_sni(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolved: list[str] = []
    observed: dict[str, object] = {}

    def resolver(*args, **kwargs):
        resolved.append("93.184.216.34" if len(resolved) == 0 else "127.0.0.1")
        return [(None, None, None, None, (resolved[-1], 443))]

    async def send(request: httpx.Request) -> httpx.Response:
        observed.update(
            url_host=request.url.host,
            host=request.headers["host"],
            sni=request.extensions["sni_hostname"],
        )
        return httpx.Response(200)

    monkeypatch.setattr("healer.connection_security.socket.getaddrinfo", resolver)
    transport = PinnedAsyncTransport(
        "https://api.example.com", env={}, inner=httpx.MockTransport(send)
    )
    request = httpx.Request("GET", "https://api.example.com/path")
    response = await transport.handle_async_request(request)
    assert response.status_code == 200
    assert observed == {
        "url_host": "93.184.216.34",
        "host": "api.example.com",
        "sni": "api.example.com",
    }
    assert len(resolved) == 1
    await transport.aclose()


@pytest.mark.asyncio
async def test_ac_106_pinned_transport_rejects_private_unallowlisted_dns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "healer.connection_security.socket.getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("127.0.0.1", 443))],
    )
    transport = PinnedAsyncTransport(
        "https://api.example.com",
        env={},
        inner=httpx.MockTransport(lambda request: httpx.Response(200)),
    )
    with pytest.raises(ValueError, match="publicly routable"):
        await transport.handle_async_request(
            httpx.Request("GET", "https://api.example.com/")
        )
    await transport.aclose()


@pytest.mark.asyncio
async def test_ac_106_exact_allowlist_still_pins_private_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[str] = []
    monkeypatch.setattr(
        "healer.connection_security.socket.getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("10.0.0.8", 443))],
    )

    async def send(request: httpx.Request) -> httpx.Response:
        observed.append(request.url.host)
        return httpx.Response(200)

    transport = PinnedAsyncTransport(
        "https://internal.example/api",
        env={"CONNECTIONS_ALLOWED_ORIGINS": "https://internal.example"},
        inner=httpx.MockTransport(send),
    )
    await transport.handle_async_request(
        httpx.Request("GET", "https://internal.example/api")
    )
    assert observed == ["10.0.0.8"]
    await transport.aclose()


@pytest.mark.asyncio
async def test_ac_106_mcp_transport_pins_ip_with_original_host_and_sni(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx2

    from healer.connection_security import PinnedHTTPX2Transport

    observed: dict[str, object] = {}
    monkeypatch.setattr(
        "healer.connection_security.socket.getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 443))],
    )

    class Inner(httpx2.AsyncBaseTransport):
        async def handle_async_request(self, request):
            observed.update(
                host=request.url.host,
                header=request.headers["host"],
                sni=request.extensions["sni_hostname"],
            )
            return httpx2.Response(200)

        async def aclose(self):
            return None

    monkeypatch.setattr(httpx2, "AsyncHTTPTransport", lambda **kwargs: Inner())
    transport = PinnedHTTPX2Transport("https://mcp.example/mcp", env={})
    await transport.handle_async_request(
        httpx2.Request("GET", "https://mcp.example/mcp")
    )
    assert observed == {
        "host": "93.184.216.34",
        "header": "mcp.example",
        "sni": "mcp.example",
    }
    await transport.aclose()


_RAW = {"paths": {"/items": {"get": {"operationId": "list_items", "responses": {}}}}}


async def _registry_for(client, config, cfg, raw=_RAW, **kwargs):
    from healer.models import LoadedSpec
    from healer.openapi_loader import operations
    from healer.registry import Registry

    loaded = LoadedSpec(
        raw, {f"api__{k}": v for k, v in operations(raw).items()}, "hash"
    )

    async def source() -> LoadedSpec:
        return loaded

    registry = Registry(client, config, cfg, spec_source=source, **kwargs)
    await registry.load()
    return registry


def _no_sleep_registry_kwargs() -> dict:
    async def sleep(_: float) -> None:
        return None

    return {"sleep": sleep, "jitter": lambda: 0.0}


@pytest.mark.asyncio
async def test_ac_106_blocked_egress_is_a_structured_non_retryable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "healer.connection_security.socket.getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("127.0.0.1", 443))],
    )
    calls: list[httpx.Request] = []
    transport = PinnedAsyncTransport(
        "https://api.example.com",
        env={},
        inner=httpx.MockTransport(
            lambda request: calls.append(request) or httpx.Response(200, json=[])
        ),
    )
    async with httpx.AsyncClient(
        transport=transport, base_url="https://api.example.com"
    ) as client:
        registry = await _registry_for(
            client,
            {"header_sources": {}, "tools": {"api__list_items": {"postchecks": []}}},
            {},
            **_no_sleep_registry_kwargs(),
        )
        result = await registry.call("api__list_items", {})
    assert result["error"] == "API_ERROR"
    assert (result["class"], result["status"]) == ("BUSINESS", "REQUEST_REFUSED")
    assert "publicly routable" in result["detail"]["reason"]
    assert calls == []


@pytest.mark.asyncio
async def test_ac_106_transient_dns_failure_is_retryable_e1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts: list[str] = []

    def failing(*args, **kwargs):
        attempts.append("dns")
        raise OSError("temporary failure")

    monkeypatch.setattr("healer.connection_security.socket.getaddrinfo", failing)
    transport = PinnedAsyncTransport(
        "https://api.example.com",
        env={},
        inner=httpx.MockTransport(lambda r: httpx.Response(200)),
    )
    async with httpx.AsyncClient(
        transport=transport, base_url="https://api.example.com"
    ) as client:
        registry = await _registry_for(
            client,
            {"header_sources": {}, "tools": {"api__list_items": {"postchecks": []}}},
            {},
            **_no_sleep_registry_kwargs(),
        )
        result = await registry.call("api__list_items", {})
    assert (result["class"], result["status"]) == ("E1", "DestinationUnresolved")
    assert len(attempts) > 1  # E1 is retried


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("address", "allowed"),
    [
        ("64:ff9b::7f00:1", False),  # NAT64 to 127.0.0.1
        ("64:ff9b::a00:1", False),  # NAT64 to 10.0.0.1
        ("fec0::1", False),  # site-local
        ("::ffff:127.0.0.1", False),
        ("64:ff9b::808:808", True),  # NAT64 to 8.8.8.8
    ],
)
async def test_ac_106_nat64_and_site_local_addresses_are_checked(address, allowed) -> None:
    from healer.connection_security import _validated_ip

    url = f"https://[{address}]/"
    if allowed:
        assert await _validated_ip(address, 443, url, {}) == address
    else:
        with pytest.raises(ValueError, match="publicly routable"):
            await _validated_ip(address, 443, url, {})
