from __future__ import annotations

import json
import signal
from typing import Self

import pytest

import start


class Process:
    next_pid = 1000

    def __init__(self, args: list[str], **kwargs: object) -> None:
        self.args = args
        self.kwargs = kwargs
        self.pid = Process.next_pid
        Process.next_pid += 1
        self.code: int | None = None
        self.waited = False

    def poll(self) -> int | None:
        return self.code

    def wait(self, timeout: float | None = None) -> int:
        self.waited = True
        self.code = self.code or 0
        return self.code


def setup(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[list[Process], list[tuple[str, bool]]]:
    processes: list[Process] = []
    ready: list[tuple[str, bool]] = []
    monkeypatch.setattr(start, "_preflight", lambda ports: None)
    monkeypatch.setattr(start, "load_dotenv", lambda *a, **kw: None)
    monkeypatch.setattr(
        start.subprocess,
        "Popen",
        lambda command, **kw: processes.append(Process(command, **kw)) or processes[-1],
    )
    monkeypatch.setattr(
        start,
        "_wait_ready",
        lambda processes, url, **kwargs: ready.append((url, kwargs.get("mcp", False))),
    )
    monkeypatch.setattr(start.time, "sleep", lambda _: None)
    return processes, ready


def test_ac_81_start_commands_environment_and_readiness_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processes, ready = setup(monkeypatch)
    monkeypatch.setenv("PORT", "9999")
    monkeypatch.setenv("HOST", "127.0.0.1")

    def interrupt(_: float) -> None:
        start.signal.getsignal(signal.SIGINT)(signal.SIGINT, None)

    monkeypatch.setattr(start.time, "sleep", interrupt)
    monkeypatch.setattr(start.os, "killpg", lambda *args: None)
    result = start.main(
        [
            "--mock-port",
            "18000",
            "--port",
            "18002",
            "--db",
            "test.db",
        ]
    )
    assert result == 0
    assert ready == [
        ("http://127.0.0.1:18000/openapi.json", False),
        ("http://127.0.0.1:18002/", False),
        ("http://127.0.0.1:18002/mcp", True),
    ]
    assert [p.args[2] for p in processes] == [
        "mock_api",
        "dashboard.unified",
    ]
    for process in processes:
        assert process.kwargs["cwd"] == start.ROOT
        assert (
            process.kwargs["env"]["PYTHONPATH"] == f"{start.ROOT / 'src'}:{start.ROOT}"
        )
        assert process.kwargs["env"]["DB_PATH"] == str(start.ROOT / "test.db")
        assert process.kwargs["env"]["PORT"] == "18002"
        assert process.kwargs["env"]["HOST"] == "127.0.0.1"
        assert process.kwargs["start_new_session"] is True
        assert process.waited
    assert "--db" in processes[1].args


def test_ac_81_start_deployment_environment_and_cli_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MOCK_PORT", "18010")
    monkeypatch.setenv("PORT", "")
    monkeypatch.setenv("DB_PATH", "/var/lib/healer/registry.db")
    monkeypatch.setenv("MCP_TOKEN_ENV", "DEPLOY_TOKEN")
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "gateway.example, localhost")
    monkeypatch.setenv("MCP_ALLOWED_ORIGINS", "https://gateway.example")
    args = start._arguments([])
    assert args.mock_port == 18010
    assert args.port == 8080
    assert args.db == start.Path("/var/lib/healer/registry.db")
    assert args.token_env == "DEPLOY_TOKEN"
    assert args.allowed_host == ["gateway.example", "localhost"]
    assert args.allowed_origin == ["https://gateway.example"]

    overridden = start._arguments(
        ["--mock-port", "18011", "--port", "18012", "--db", "cli.db", "--token-env", "CLI_TOKEN", "--allowed-host", "cli.example", "--allowed-origin", "https://cli.example"]
    )
    assert overridden.mock_port == 18011
    assert overridden.port == 18012
    assert overridden.db == start.Path("cli.db")
    assert overridden.token_env == "CLI_TOKEN"
    assert overridden.allowed_host == ["cli.example"]
    assert overridden.allowed_origin == ["https://cli.example"]


def test_ac_81_start_rejects_duplicate_and_busy_ports_without_spawning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        start.subprocess, "Popen", lambda *a, **kw: pytest.fail("spawned")
    )
    assert start.main(["--mock-port", "18000", "--port", "18000"]) == 1

    class BusySocket:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def bind(self, address: tuple[str, int]) -> None:
            raise OSError("busy")

    monkeypatch.setattr(start.socket, "socket", BusySocket)
    with pytest.raises(ValueError, match="unavailable"):
        start._preflight([18000])


def test_ac_81_start_readiness_failure_cleans_started_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processes, _ = setup(monkeypatch)
    monkeypatch.setattr(
        start,
        "_wait_ready",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("not ready")),
    )
    killed: list[int] = []
    monkeypatch.setattr(
        start.os,
        "killpg",
        lambda pid, sig: (
            killed.append(pid)
            if sig != 0
            else (_ for _ in ()).throw(ProcessLookupError())
        ),
    )
    assert start.main(["--mock-port", "18000", "--port", "18002"]) == 1
    assert len(processes) == 1 and processes[0].waited and killed == [processes[0].pid]


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
def test_ac_81_start_signal_shuts_down_process_groups(
    monkeypatch: pytest.MonkeyPatch, signum: signal.Signals
) -> None:
    processes, _ = setup(monkeypatch)
    kills: list[tuple[int, signal.Signals]] = []
    monkeypatch.setattr(
        start.os,
        "killpg",
        lambda pid, sig: (
            kills.append((pid, sig))
            if sig
            else (_ for _ in ()).throw(ProcessLookupError())
        ),
    )

    def interrupt(_: float) -> None:
        start.signal.getsignal(signum)(signum, None)

    monkeypatch.setattr(start.time, "sleep", interrupt)
    assert start.main(["--mock-port", "18000", "--port", "18002"]) == 0
    assert len(processes) == 2 and len(kills) == 2
    assert all(sig == signal.SIGTERM for _, sig in kills)


def test_ac_81_start_unexpected_exit_returns_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processes, _ = setup(monkeypatch)
    monkeypatch.setattr(
        start.os,
        "killpg",
        lambda pid, sig: None if sig else (_ for _ in ()).throw(ProcessLookupError()),
    )

    def exit_after_start(_: float) -> None:
        processes[0].code = 2

    monkeypatch.setattr(start.time, "sleep", exit_after_start)
    assert start.main(["--mock-port", "18000", "--port", "18002"]) == 1
    assert all(process.waited for process in processes)


def test_ac_81_start_cancel_during_readiness_does_not_spawn_later_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wait_ready = start._wait_ready
    processes, _ = setup(monkeypatch)

    def not_ready(url: str, *, mcp: bool = False, **kwargs: object) -> bool:
        start.signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
        return False

    monkeypatch.setattr(start, "_wait_ready", wait_ready)
    monkeypatch.setattr(start, "_ready", not_ready)
    monkeypatch.setattr(start.os, "killpg", lambda *args: None)
    assert start.main(["--mock-port", "18000", "--port", "18002"]) == 0
    assert len(processes) == 1


def test_ac_81_start_detects_earlier_service_dying_during_readiness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wait_ready = start._wait_ready
    processes, _ = setup(monkeypatch)
    monkeypatch.setattr(start, "_wait_ready", wait_ready)

    processes.extend(
        [
            Process(["python", "-m", "mock_api"]),
            Process(["python", "-m", "healer.mcp_server"]),
        ]
    )
    processes[0].code = 3
    with pytest.raises(RuntimeError, match="exited before becoming ready"):
        start._wait_ready(processes, "http://127.0.0.1:18001/mcp")


def test_ac_81_start_wait_ready_cancels_immediately() -> None:
    process = Process(["python", "-m", "mock_api"])
    with pytest.raises(InterruptedError):
        start._wait_ready([process], "http://127.0.0.1:8000", cancelled=lambda: True)


def test_ac_81_start_mcp_readiness_validates_jsonrpc_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        status = 200

        def __init__(self) -> None:
            self.headers = {"content-type": "application/json"}

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, limit: int) -> bytes:
            return json.dumps(payload).encode()

    payload = {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2024-11-05"}}
    monkeypatch.setattr(start, "urlopen", lambda *args, **kwargs: Response())
    assert start._ready("http://127.0.0.1:8001/mcp", mcp=True)
    payload = {"jsonrpc": "2.0", "id": 1, "error": {"code": -1}}
    assert not start._ready("http://127.0.0.1:8001/mcp", mcp=True)


def test_ac_81_start_stop_kills_group_after_leader_exits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = Process(["python"])
    process.code = 0
    kills: list[tuple[int, int]] = []
    monkeypatch.setattr(
        start.os,
        "killpg",
        lambda pid, sig: kills.append((pid, sig)) if sig else None,
    )
    start._stop([process])
    assert kills == [(process.pid, signal.SIGTERM), (process.pid, signal.SIGKILL)]


def test_ac_81_start_wait_ready_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    process = Process(["python", "-m", "mock_api"])
    ticks = iter([0, 31])
    monkeypatch.setattr(start.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(start, "_ready", lambda *args, **kwargs: False)
    with pytest.raises(RuntimeError, match="timed out"):
        start._wait_ready([process], "http://127.0.0.1:8000", cancelled=lambda: False)
