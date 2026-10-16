"""Runtime-only connection auth and egress policy."""

from __future__ import annotations

import asyncio
import ipaddress
import os
import re
import socket
from collections.abc import Mapping
from urllib.parse import urlsplit

import httpx

_ENV = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_HEADER = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_FORBIDDEN_HEADERS = {
    "host",
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
_SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie", "x-api-key"}


def _sensitive_header(name: str) -> bool:
    lowered = name.casefold()
    return lowered in _SENSITIVE_HEADERS or any(
        word in lowered
        for word in ("token", "secret", "password", "api-key", "api_key")
    )


def _env(name: object, env: Mapping[str, str]) -> str:
    if not isinstance(name, str) or not _ENV.fullmatch(name) or not env.get(name):
        safe_name = (
            name if isinstance(name, str) and _ENV.fullmatch(name) else "configured"
        )
        raise ValueError(f"environment variable {safe_name} is not set")
    value = env[name]
    _header_value(value)
    return value


def _header_value(value: object) -> str:
    if not isinstance(value, str) or any(ord(c) < 32 or ord(c) > 126 for c in value):
        raise ValueError("unsafe configured header value")
    return value


def _header_name(name: object) -> str:
    if not isinstance(name, str) or not _HEADER.fullmatch(name):
        raise ValueError("unsafe configured header")
    folded = name.lower()
    if folded in _FORBIDDEN_HEADERS or folded.startswith("proxy-"):
        raise ValueError("unsafe configured header")
    return name


def resolve_headers(entry: dict, env: Mapping[str, str]) -> dict[str, str]:
    """Resolve operator-held values per connection; never place these in tool config."""
    headers: dict[str, str] = {}
    folded: set[str] = set()

    def add(name: object, value: str) -> None:
        safe = _header_name(name)
        key = safe.casefold()
        if key in folded:
            raise ValueError("duplicate configured header")
        folded.add(key)
        headers[safe] = value

    for name, value in entry.get("headers", {}).items():
        if _sensitive_header(name):
            raise ValueError("sensitive header values must use secret_headers")
        value = _header_value(value)
        add(name, value)
    for name, var in entry.get("secret_headers", {}).items():
        add(name, _env(var, env))
    auth = entry.get("auth")
    if auth is None and entry.get("token_env"):
        auth = {"type": "bearer", "token_env": entry["token_env"]}
    if auth:
        kind = auth["type"]
        if kind == "bearer":
            add("Authorization", f"Bearer {_env(auth.get('token_env'), env)}")
        elif kind == "api_key":
            add(auth.get("header"), _env(auth.get("value_env"), env))
        elif kind == "basic":
            import base64

            raw = f"{_env(auth.get('username_env'), env)}:{_env(auth.get('password_env'), env)}"
            add("Authorization", "Basic " + base64.b64encode(raw.encode()).decode())
        elif kind != "none":
            raise ValueError("unsupported auth type")
    return headers


def has_credentials(entry: dict) -> bool:
    auth = entry.get("auth") or (
        {} if not entry.get("token_env") else {"type": "bearer"}
    )
    return bool(entry.get("secret_headers")) or auth.get("type", "none") != "none"


def validate_entry_auth(entry: dict) -> None:
    """Validate auth/reference shape without resolving or rewriting config."""
    for key in ("auth", "spec_auth"):
        auth = entry.get(key)
        if auth is None:
            continue
        if not isinstance(auth, dict) or auth.get("type") not in {
            "none",
            "bearer",
            "api_key",
            "basic",
        }:
            raise ValueError("invalid auth profile")
        kind = auth["type"]
        allowed = {
            "none": {"type"},
            "bearer": {"type", "token_env"},
            "api_key": {"type", "header", "value_env"},
            "basic": {"type", "username_env", "password_env"},
        }[kind]
        if set(auth) != allowed:
            raise ValueError("invalid auth profile fields")
        required = {
            "bearer": ("token_env",),
            "api_key": ("header", "value_env"),
            "basic": ("username_env", "password_env"),
        }.get(kind, ())
        if any(
            not isinstance(auth.get(k), str) or not _ENV.fullmatch(auth[k])
            for k in required
            if k.endswith("_env")
        ):
            raise ValueError("invalid auth environment reference")
        if kind == "api_key":
            _header_name(auth.get("header"))
    if entry.get("auth") is not None and entry.get("token_env"):
        raise ValueError("conflicting auth profiles")
    for collection in ("headers", "secret_headers"):
        values = entry.get(collection, {})
        if not isinstance(values, dict):
            raise ValueError("configured headers must be an object")  # noqa: TRY004 - config validation
        names = set()
        for name, value in values.items():
            _header_name(name)
            if name.casefold() in names:
                raise ValueError("duplicate configured header")
            names.add(name.casefold())
            if collection == "headers" and _sensitive_header(name):
                raise ValueError("sensitive header values must use secret_headers")
            if collection == "headers":
                _header_value(value)
            if collection == "secret_headers" and (
                not isinstance(value, str) or not _ENV.fullmatch(value)
            ):
                raise ValueError("invalid secret header environment reference")
    literal = {name.casefold() for name in entry.get("headers", {})}
    secret = {name.casefold() for name in entry.get("secret_headers", {})}
    if literal & secret:
        raise ValueError("duplicate configured header")
    resolved_names = set(entry.get("headers", {})) | set(
        entry.get("secret_headers", {})
    )
    auth = entry.get("auth") or ({"type": "bearer"} if entry.get("token_env") else {})
    if auth.get("type") in {"bearer", "basic"} and any(
        x.casefold() == "authorization" for x in resolved_names
    ):
        raise ValueError("duplicate configured header")
    if auth.get("type") == "api_key" and auth["header"].casefold() in {
        x.casefold() for x in resolved_names
    }:
        raise ValueError("duplicate configured header")


def origin(url: str) -> tuple[str, str, int]:
    parts = urlsplit(url)
    return (
        parts.scheme.lower(),
        (parts.hostname or "").lower(),
        parts.port or (443 if parts.scheme == "https" else 80),
    )


def check_egress(
    url: str,
    *,
    credentials: bool = False,
    mock_transport: bool = False,
    env: Mapping[str, str] = os.environ,
) -> None:
    """Reject unsafe destinations. Injected test transports bypass DNS only."""
    try:
        parts = urlsplit(url)
        _ = parts.port
    except ValueError:
        raise ValueError("unsafe connection destination") from None
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("unsafe connection destination")
    if (
        parts.username
        or parts.password
        or parts.fragment
        or any(c in url for c in "\r\n")
    ):
        raise ValueError("unsafe connection destination")
    if (
        credentials
        and parts.scheme != "https"
        and not _allowed_origin(url, env)
        and not mock_transport
    ):
        raise ValueError("credentials require HTTPS or an allowed origin")
    if mock_transport or _allowed_origin(url, env):
        return


def _allowed_origin(url: str, env: Mapping[str, str]) -> bool:
    target = origin(url)
    for item in env.get("CONNECTIONS_ALLOWED_ORIGINS", "").split(","):
        item = item.strip()
        if item:
            try:
                parts = urlsplit(item)
                if (
                    parts.path not in ("", "/")
                    or parts.query
                    or parts.fragment
                    or parts.username
                    or parts.password
                ):
                    continue
                if origin(item) == target:
                    return True
            except ValueError:
                continue
    return False


async def _validated_ip(host: str, port: int, url: str, env: Mapping[str, str]) -> str:
    try:
        ip = ipaddress.ip_address(host)
        addresses = [ip]
    except ValueError:
        try:
            records = await asyncio.to_thread(
                socket.getaddrinfo, host, port, type=socket.SOCK_STREAM
            )
            addresses = list({ipaddress.ip_address(record[4][0]) for record in records})
        except (OSError, ValueError):
            raise ValueError("connection destination could not be validated") from None
    if not addresses or (
        not _allowed_origin(url, env) and any(not ip.is_global for ip in addresses)
    ):
        raise ValueError("connection destination is not publicly routable")
    return str(min(addresses, key=lambda ip: (ip.version, int(ip))))


class PinnedAsyncTransport(httpx.AsyncBaseTransport):
    """Resolve and validate each target, then dial only the selected numeric address."""

    def __init__(
        self,
        expected_url: str,
        *,
        env: Mapping[str, str] = os.environ,
        credentials: bool = False,
        inner: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.expected = origin(expected_url)
        self.env, self.credentials = env, credentials
        self.inner = inner
        self._pools: dict[str, httpx.AsyncBaseTransport] = {}

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        original = str(request.url)
        if origin(original) != self.expected:
            raise ValueError("request target outside connection origin")
        check_egress(original, credentials=self.credentials, env=self.env)
        host = request.url.host
        port = request.url.port or (443 if request.url.scheme == "https" else 80)
        ip = await _validated_ip(host, port, original, self.env)
        if self.inner is not None:
            transport = self.inner
        else:
            transport = self._pools.get(ip)
            if transport is None:
                transport = httpx.AsyncHTTPTransport(trust_env=False)
                self._pools[ip] = transport
        request.headers.setdefault("host", request.url.netloc.decode("ascii"))
        request.extensions["sni_hostname"] = host
        request.url = request.url.copy_with(host=ip)
        return await transport.handle_async_request(request)

    async def aclose(self) -> None:
        transports = set(self._pools.values())
        if self.inner is not None:
            transports.add(self.inner)
        await asyncio.gather(*(transport.aclose() for transport in transports))


def no_redirect_client(**kwargs: object) -> httpx.AsyncClient:
    base_url = kwargs.get("base_url")
    expected = origin(str(base_url)) if base_url else None
    env = kwargs.pop("egress_env", os.environ)
    credentials = bool(kwargs.pop("egress_credentials", kwargs.get("headers")))
    injected = kwargs.get("transport")
    if expected is not None and injected is None:
        kwargs["transport"] = PinnedAsyncTransport(
            str(base_url), env=env, credentials=credentials
        )

    async def scope(request: httpx.Request) -> None:
        if expected is not None and origin(str(request.url)) != expected:
            raise ValueError("request target outside connection origin")

    hooks = kwargs.pop("event_hooks", {}) or {}
    hooks = {**hooks, "request": [scope, *hooks.get("request", [])]}
    return httpx.AsyncClient(
        follow_redirects=False, trust_env=False, event_hooks=hooks, **kwargs
    )


def no_redirect_httpx2(
    url: str,
    headers: Mapping[str, str],
    transport: object | None = None,
    *,
    env: Mapping[str, str] = os.environ,
    credentials: bool = False,
):
    import httpx2

    expected = origin(url)

    async def scope(request: object) -> None:
        if origin(str(request.url)) != expected:
            raise ValueError("request target outside connection origin")

    pinned = (
        PinnedHTTPX2Transport(url, env=env, credentials=credentials)
        if transport is None
        else transport
    )

    return httpx2.AsyncClient(
        headers=dict(headers),
        transport=pinned,
        follow_redirects=False,
        trust_env=False,
        event_hooks={"request": [scope]},
    )


class PinnedHTTPX2Transport:
    def __new__(
        cls,
        expected_url: str,
        *,
        env: Mapping[str, str] = os.environ,
        credentials: bool = False,
    ):
        import httpx2

        class Transport(httpx2.AsyncBaseTransport):
            def __init__(self) -> None:
                self.expected = origin(expected_url)
                self.pools: dict[str, object] = {}

            async def handle_async_request(self, request: object):
                original = str(request.url)
                if origin(original) != self.expected:
                    raise ValueError("request target outside connection origin")
                check_egress(original, credentials=credentials, env=env)
                host = request.url.host
                port = request.url.port or (
                    443 if request.url.scheme == "https" else 80
                )
                ip = await _validated_ip(host, port, original, env)
                transport = self.pools.get(ip)
                if transport is None:
                    transport = httpx2.AsyncHTTPTransport(trust_env=False)
                    self.pools[ip] = transport
                request.headers.setdefault("host", request.url.netloc.decode("ascii"))
                request.extensions["sni_hostname"] = host
                request.url = request.url.copy_with(host=ip)
                return await transport.handle_async_request(request)

            async def aclose(self) -> None:
                await asyncio.gather(*(pool.aclose() for pool in self.pools.values()))

        return Transport()
