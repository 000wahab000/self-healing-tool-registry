"""Regression tests for the 2026-10-16 code review fixes."""

from __future__ import annotations

from healer.jev import render_option


def test_jev_renders_enum_map_and_encoding_options():
    text = render_option(
        {
            "request_ops": [
                {
                    "op": "enum_map",
                    "path": ["body", "kind"],
                    "mapping": {"work": "WORK"},
                },
                {"op": "encoding", "content_type": "application/x-www-form-urlencoded"},
            ],
            "response_ops": [],
        }
    )
    assert "body.kind" in text and "application/x-www-form-urlencoded" in text
