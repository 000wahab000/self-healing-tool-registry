"""Canonical JSON, hashing and path helpers for nested dict/list documents."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from healer.models import Path


def dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256(obj: Any) -> str:
    return hashlib.sha256(dumps(obj).encode()).hexdigest()


def _step(node: Any, key: str | int) -> Any:
    if isinstance(node, dict) and key in node:
        return node[key]
    if isinstance(node, list) and isinstance(key, int) and 0 <= key < len(node):
        return node[key]
    raise KeyError(key)


def get(doc: Any, path: Path) -> Any:
    for key in path:
        doc = _step(doc, key)
    return doc


def pop(doc: Any, path: Path) -> Any:
    get(doc, path)  # KeyError if missing, so the container pop below cannot fail
    return get(doc, path[:-1]).pop(path[-1])


def put(doc: Any, path: Path, value: Any) -> None:
    node = doc
    for key in path[:-1]:
        node = node.setdefault(key, {}) if isinstance(node, dict) else _step(node, key)
    if isinstance(node, dict) or (
        isinstance(node, list)
        and isinstance(path[-1], int)
        and 0 <= path[-1] < len(node)
    ):
        node[path[-1]] = value
    else:
        raise KeyError(path[-1])
