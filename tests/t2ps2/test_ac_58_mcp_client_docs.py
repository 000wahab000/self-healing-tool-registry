"""AC-58: consolidated README MCP client setup stays usable and contract-aligned."""

from __future__ import annotations

import contextlib
import io
import json
import re
from pathlib import Path

from healer import mcp_server

ROOT = Path(__file__).parents[2]
README = ROOT / "README.md"
AGENTS = ROOT / "AGENTS.md"
MCP_SECTION = re.compile(r"^## MCP client setup\n(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)


def _section() -> str:
    match = MCP_SECTION.search(README.read_text(encoding="utf-8"))
    assert match is not None
    return match.group(1)


def _json_configs() -> list[dict]:
    section = _section()
    configs = [json.loads(block) for block in re.findall(r"```json\n(.*?)```", section, re.DOTALL)]
    without_fences = re.sub(r"```json\n.*?```", "", section, flags=re.DOTALL)
    decoder = json.JSONDecoder()
    for match in re.finditer(r'\{"mcpServers"\s*:', without_fences):
        config, _ = decoder.raw_decode(without_fences[match.start():])
        configs.append(config)
    return configs


def _server_flags() -> set[str]:
    """The CLI flags the server actually accepts, read from its argparse help."""
    buf = io.StringIO()
    with contextlib.suppress(SystemExit), contextlib.redirect_stdout(buf):
        mcp_server._arguments(["--help"])
    return set(re.findall(r"--[a-z][a-z-]*", buf.getvalue()))


def test_ac_58_client_setup_uses_canonical_sources():
    assert README.is_file() and AGENTS.is_file()
    section = _section()
    requirements = AGENTS.read_text(encoding="utf-8")
    assert "README.md" in requirements
    assert "FR-19.1" in requirements and "AC-58" in requirements
    for name in ("Claude Desktop", "Cursor", "Windsurf"):
        assert name in section
    assert "Merge this full entry" in section
    assert "Streamable HTTP" in section


def test_ac_58_parses_full_mcpservers_configs_for_both_http_clients():
    configs = _json_configs()
    assert configs
    http_configs = [c for c in configs if "mcpServers" in c]
    assert len(http_configs) >= 2
    server_entries = [entry for config in http_configs for entry in config["mcpServers"].values()]
    assert any("url" in entry for entry in server_entries)
    assert any("serverUrl" in entry for entry in server_entries)
    for config in http_configs:
        assert config["mcpServers"]


def test_ac_58_shared_stdio_entry_launches_server_for_all_three_clients():
    configs = _json_configs()
    stdio = [
        entry
        for config in configs
        for entry in config["mcpServers"].values()
        if "command" in entry
    ]
    assert len(stdio) == 1  # README documents one shared entry for all three clients.
    args = stdio[0]["args"]
    assert args[args.index("-m") + 1] == "healer.mcp_server"


def test_ac_58_documented_mcp_flags_exist_on_server():
    documented = set(re.findall(r"--[a-z][a-z-]*", _section()))
    assert documented
    assert documented <= _server_flags()


def test_ac_58_no_secret_values_and_env_reference_guidance():
    section = _section()
    assert not re.search(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}", section)
    assert "sk-" not in section
    assert "--token-env" in section
    assert "HEALER_MCP_TOKEN" in section


def test_ac_58_console_command_is_pending_and_ui_check_is_honest():
    section = _section()
    assert "healer-mcp" in section
    assert "approval" in section
    assert "manual client-UI verification is outstanding" in section
