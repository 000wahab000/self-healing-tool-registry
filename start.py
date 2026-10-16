from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
READY_TIMEOUT = 30
STOP_TIMEOUT = 5


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the local tool registry stack")
    parser.add_argument("--mock-port", type=int, default=int(os.environ.get("MOCK_PORT") or 8000))
    parser.add_argument(
        "--port",
        "--dashboard-port",
        dest="port",
        type=int,
        default=int(os.environ.get("PORT") or 8080),
    )
    parser.add_argument("--mcp-port", help=argparse.SUPPRESS)
    parser.add_argument(
        "--host",
        default=os.environ.get("HOST")
        or ("0.0.0.0" if "PORT" in os.environ else "127.0.0.1"),
    )
    parser.add_argument("--token-env", default=os.environ.get("MCP_TOKEN_ENV"))
    parser.add_argument("--allowed-host", action="append")
    parser.add_argument("--allowed-origin", action="append")
    parser.add_argument("--db", type=Path, default=Path(os.environ.get("DB_PATH") or ROOT / "healer.db"))
    args = parser.parse_args(argv)
    if args.mcp_port is not None:
        parser.error("--mcp-port is no longer separate; use --port")
    args.allowed_host = args.allowed_host or _env_list("MCP_ALLOWED_HOSTS")
    args.allowed_origin = args.allowed_origin or _env_list("MCP_ALLOWED_ORIGINS")
    return args


def _env_list(name: str) -> list[str] | None:
    values = [value.strip() for value in os.environ.get(name, "").split(",") if value.strip()]
    return values or None


def _preflight(ports: list[int]) -> None:
    if len(set(ports)) != len(ports):
        raise ValueError("mock and dashboard ports must be distinct")
    for port in ports:
        if not 1 <= port <= 65535:
            raise ValueError(f"invalid port: {port}")
        with socket.socket() as probe:
            try:
                probe.bind(("0.0.0.0", port))
            except OSError as exc:
                raise ValueError(f"port {port} is unavailable") from exc


def _command(name: str, args: argparse.Namespace) -> list[str]:
    if name == "mock":
        return [sys.executable, "-m", "mock_api"]
    command = [
        sys.executable,
        "-m",
        "dashboard.unified",
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--base-url",
        f"http://127.0.0.1:{args.mock_port}",
        "--tools",
        str(ROOT / "config/tools.json"),
        "--db",
        str(args.db),
        "--mcp-servers",
        str(ROOT / "config/mcp_servers.json"),
    ]
    for flag, values in (
        ("--allowed-host", args.allowed_host),
        ("--allowed-origin", args.allowed_origin),
    ):
        for value in values or []:
            command.extend((flag, value))
    if args.token_env:
        command.extend(("--token-env", args.token_env))
    return command


def _readiness_host(args: argparse.Namespace) -> str:
    if args.host in ("0.0.0.0", "::"):
        return (args.allowed_host or ["127.0.0.1"])[0].removesuffix(":*")
    return args.host


def _connect_host(args: argparse.Namespace) -> str:
    return "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host


def _display_host(host: str) -> str:
    return "127.0.0.1" if host in ("0.0.0.0", "::") else host


def _ready(
    url: str, *, mcp: bool = False, host: str | None = None, token: str | None = None
) -> bool:
    try:
        if mcp:
            request = Request(
                url,
                data=b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"startup-check","version":"1"}}}',
                headers={
                    "content-type": "application/json",
                    "accept": "application/json, text/event-stream",
                    **({"host": host} if host else {}),
                    **({"authorization": f"Bearer {token}"} if token else {}),
                },
            )
            with urlopen(request, timeout=1) as response:
                if response.status != 200 or "json" not in response.headers.get(
                    "content-type", ""
                ):
                    return False
                message = json.loads(response.read(65536))
                return (
                    isinstance(message, dict)
                    and message.get("jsonrpc") == "2.0"
                    and message.get("id") == 1
                    and isinstance(message.get("result"), dict)
                    and isinstance(message["result"].get("protocolVersion"), str)
                    and "error" not in message
                )
        request = Request(url, headers={"host": host} if host else {})
        with urlopen(request, timeout=1) as response:
            return response.status == 200
    except (OSError, URLError, ValueError):
        return False


def _wait_ready(
    processes: list[subprocess.Popen[bytes]],
    url: str,
    *,
    mcp: bool = False,
    cancelled: Callable[[], bool] = lambda: False,
    host: str | None = None,
    token: str | None = None,
) -> None:
    deadline = time.monotonic() + READY_TIMEOUT
    while time.monotonic() < deadline:
        if cancelled():
            raise InterruptedError
        exited = next(
            (process for process in processes if process.poll() is not None), None
        )
        if exited:
            raise RuntimeError(
                f"service exited before becoming ready: {exited.args[2]}"
            )
        if _ready(url, mcp=mcp, host=host, token=token):
            if cancelled():
                raise InterruptedError
            if any(process.poll() is not None for process in processes):
                raise RuntimeError("service exited during startup")
            return
        time.sleep(0.2)
    raise RuntimeError(f"service readiness timed out: {url}")


def _stop(processes: list[subprocess.Popen[bytes]]) -> None:
    if os.name != "posix":
        raise RuntimeError("start.py requires POSIX process groups")
    for process in reversed(processes):
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + STOP_TIMEOUT
    for process in reversed(processes):
        try:
            process.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            pass
    # Leaders may exit while gateway-owned subprocesses remain in their group.
    for process in reversed(processes):
        try:
            os.killpg(process.pid, 0)
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    for process in processes:
        if process.poll() is None:
            process.wait()


def main(argv: list[str] | None = None) -> int:
    load_dotenv(ROOT / ".env", override=False)
    args = _arguments(argv)
    args.db = args.db if args.db.is_absolute() else ROOT / args.db
    if os.name != "posix":
        print("startup failed: start.py requires POSIX process groups", file=sys.stderr)
        return 1
    try:
        _preflight([args.mock_port, args.port])
    except ValueError as exc:
        print(f"startup failed: {exc}", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(ROOT / "src"), str(ROOT)))
    env.update(
        {
            "MOCK_PORT": str(args.mock_port),
            "PORT": str(args.port),
            "HOST": args.host,
            "DB_PATH": str(args.db),
        }
    )
    processes: list[subprocess.Popen[bytes]] = []
    interrupted = False
    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}

    def stop_signal(_signum: int, _frame: object) -> None:
        nonlocal interrupted
        interrupted = True

    for sig in previous:
        signal.signal(sig, stop_signal)
    try:
        for name, port, endpoints in (
            ("mock", args.mock_port, [("/openapi.json", False)]),
            ("unified", args.port, [("/", False), ("/mcp", True)]),
        ):
            if interrupted:
                break
            processes.append(
                subprocess.Popen(
                    _command(name, args), cwd=ROOT, env=env, start_new_session=True
                )
            )
            for path, mcp in endpoints:
                _wait_ready(
                    processes,
                    f"http://{_connect_host(args) if name == 'unified' else '127.0.0.1'}:{port}{path}",
                    mcp=mcp,
                    cancelled=lambda: interrupted,
                    host=_readiness_host(args) if name == "unified" else None,
                    token=os.environ.get(args.token_env) if args.token_env else None,
                )
                if interrupted:
                    break
        if not interrupted:
            if any(process.poll() is not None for process in processes):
                raise RuntimeError("service exited during startup")
            print(f"Mock API:   http://127.0.0.1:{args.mock_port}", flush=True)
            print(
                f"Dashboard + MCP: http://{_display_host(args.host)}:{args.port}",
                flush=True,
            )
        while not interrupted:
            exited = next(
                (process for process in processes if process.poll() is not None), None
            )
            if exited:
                raise RuntimeError(f"service exited unexpectedly: {exited.args[2]}")
            time.sleep(0.2)
    except InterruptedError:
        return_code = 0
    except (RuntimeError, OSError) as exc:
        print(f"startup failed: {exc}", file=sys.stderr)
        return_code = 1
    else:
        return_code = 0
    finally:
        _stop(processes)
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
