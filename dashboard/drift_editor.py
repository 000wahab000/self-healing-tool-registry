"""Turn an edited input schema into the mock's custom drift spec (dashboard-only).

The Live tab shows a tool's real v1 input schema next to an editable copy. The diff
becomes `{"tool", "rename", "to_int", "wrap", "require", "header"}`, the shape
`mock_api.app.check_custom` validates and the mock serves. Only the mock is told; the
registry still has to discover and heal the change on its own.
"""

from __future__ import annotations

from mock_api.app import check_custom

SUPPORTED = (
    "rename one property (same type), change one property's type from string to integer, "
    "move all properties under one new object property (wrap), add one new required "
    "string property, and set a required header. Other edits (deleting a field, other "
    "type changes, nested or constraint edits) are not supported."
)
_NOTES = ("title", "description")  # labels only; never part of the contract


def _props(schema: dict, what: str) -> dict[str, dict]:
    props = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(props, dict) or not all(isinstance(v, dict) for v in props.values()):
        raise ValueError(f"{what} must be a JSON object schema with a 'properties' object")
    return props


def _core(prop: dict, *, drop_type: bool = False) -> dict:
    skip = (*_NOTES, "type") if drop_type else _NOTES
    return {k: v for k, v in prop.items() if k not in skip}


def custom_from_schema(
    tool: str, actual: dict, fake: dict, header: str | None = None
) -> dict:
    """Diff `fake` against `actual` and return a validated custom drift spec.

    Pairing rule: removed and added properties of the same type (or string to integer) are paired in schema
    order, so renaming `a` to `x` while another same-typed property is also added is
    read as a rename of the first removed to the first added. A leftover added property
    becomes the new required one. Raises ValueError for anything else, listing what
    is supported.
    """
    base = _props(actual, "actual schema")
    new = _props(fake, "fake schema")
    spec: dict = {"tool": tool, "rename": {}}
    required = set(fake.get("required") or [])

    # Wrap: one new object property that holds every other property.
    wrapper = next(iter(new)) if len(new) == 1 else None
    if (
        wrapper
        and wrapper not in base
        and new[wrapper].get("type") == "object"
        and isinstance(new[wrapper].get("properties"), dict)
        and all(p.get("type") != "object" for p in base.values())
    ):
        spec["wrap"] = wrapper
        required = set(new[wrapper].get("required") or [])
        new = _props(new[wrapper], "wrapped schema")

    removed = [n for n in base if n not in new]
    added = [n for n in new if n not in base]
    pairs: dict[str, str] = {}
    for old in removed:
        match = next(
            (
                a
                for a in added
                if a not in pairs.values()
                and (base[old].get("type"), new[a].get("type"))
                in ((new[a].get("type"),) * 2, ("string", "integer"))
                and _core(new[a], drop_type=True) == _core(base[old], drop_type=True)
            ),
            None,
        )
        if match is None:
            raise ValueError(
                f"property {old!r} was removed and nothing of the same type replaces it. "
                f"Supported: {SUPPORTED}"
            )
        pairs[old] = match
    spec["rename"] = pairs
    extra = [a for a in added if a not in pairs.values()]
    if len(extra) > 1:
        raise ValueError(f"only one new required property is supported, got {extra}. {SUPPORTED}")
    if extra:
        if new[extra[0]].get("type") != "string" or extra[0] not in required:
            raise ValueError(
                f"new property {extra[0]!r} must be a required string. Supported: {SUPPORTED}"
            )
        spec["require"] = extra[0]

    renamed_to = {v: k for k, v in pairs.items()}
    ints = []
    for name, prop in new.items():
        if name == spec.get("require"):
            continue
        old = renamed_to.get(name, name)
        before = base[old]
        if before.get("type") == prop.get("type"):
            if _core(before) != _core(prop):
                raise ValueError(f"property {name!r} changed beyond its name or type. {SUPPORTED}")
        elif (before.get("type"), prop.get("type")) == ("string", "integer") and _core(
            before, drop_type=True
        ) == _core(prop, drop_type=True):
            ints.append(old)
        else:
            raise ValueError(
                f"property {name!r} changed type {before.get('type')!r} -> "
                f"{prop.get('type')!r}. Supported: {SUPPORTED}"
            )
    if len(ints) > 1:
        raise ValueError(f"only one property can change to integer, got {ints}. {SUPPORTED}")
    if ints:
        spec["to_int"] = ints[0]

    want = {renamed_to.get(n, n) for n in required} - {spec.get("require")}
    if want != set(actual.get("required") or []):
        raise ValueError(f"changing which properties are required is not supported. {SUPPORTED}")
    if header and header.strip():
        spec["header"] = header.strip()
    if not (spec["rename"] or {k for k in spec if k not in ("tool", "rename")}):
        raise ValueError(f"the fake schema equals the actual one; change something. {SUPPORTED}")
    return check_custom(spec)
