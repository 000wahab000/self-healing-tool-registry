"""AC-58: docs/mcp-clients.md is a usable client guide derived from the hand-off (FR-19)."""

from __future__ import annotations

import contextlib
import io
import json
import re
from pathlib import Path

from healer import mcp_server

ROOT = Path(__file__).parents[2]
DOC = ROOT / "docs" / "mcp-clients.md"
HANDOFF = ROOT / "tests" / "mcp" / "client-handoff.md"


def _text() -> str:
    return DOC.read_text(encoding="utf-8")


def _json_blocks() -> list[dict]:
    blocks = re.findall(r"```json\n(.*?)```", _text(), re.DOTALL)
    return [json.loads(block) for block in blocks]


def _server_flags() -> set[str]:
    """The CLI flags the server actually accepts, read from its argparse help."""
    buf = io.StringIO()
    with contextlib.suppress(SystemExit), contextlib.redirect_stdout(buf):
        mcp_server._arguments(["--help"])
    return set(re.findall(r"--[a-z][a-z-]*", buf.getvalue()))


def test_ac_58_guide_is_derived_from_the_handoff():
    assert DOC.is_file()
    assert HANDOFF.is_file()
    text = _text()
    assert "tests/mcp/client-handoff.md" in text
    for name in ("Claude Desktop", "Cursor", "Windsurf"):
        assert name in text


def test_ac_58_covers_both_transports():
    text = _text()
    assert "stdio" in text
    assert "Streamable HTTP" in text
    assert "healer.mcp_server" in text


def test_ac_58_json_snippets_parse_and_name_servers():
    blocks = _json_blocks()
    assert len(blocks) >= 5  # three stdio clients plus two HTTP clients
    for block in blocks:
        assert block["mcpServers"]


def test_ac_58_stdio_snippets_launch_the_server():
    stdio = [
        spec
        for block in _json_blocks()
        for spec in block["mcpServers"].values()
        if "command" in spec
    ]
    assert len(stdio) >= 3
    for spec in stdio:
        args = spec["args"]
        assert args[args.index("-m") + 1] == "healer.mcp_server"


def test_ac_58_documented_flags_exist_on_the_server():
    documented = set(re.findall(r"--[a-z][a-z-]*", _text()))
    assert documented  # the guide names the server's flags
    assert documented <= _server_flags()


def test_ac_58_no_secret_values():
    text = _text()
    assert not re.search(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}", text)
    assert "sk-" not in text
    assert "--token-env" in text
    assert "HEALER_MCP_TOKEN" in text


def test_ac_58_states_console_command_is_pending():
    text = _text()
    assert "healer-mcp" in text
    assert "approval" in text
