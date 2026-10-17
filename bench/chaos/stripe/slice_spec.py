import copy
import json
import sys

KEEP = [("/v1/customers","get"),("/v1/customers","post"),("/v1/customers/{customer}","get")]
def refs(o, out):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "$ref" and isinstance(v, str) and v.startswith("#/components/"): out.add(v)
            else: refs(v, out)
    elif isinstance(o, list):
        for v in o: refs(v, out)
def slice_spec(spec):
    out = {"openapi": spec["openapi"], "info": spec["info"], "servers": [{"url": "https://api.stripe.com"}], "paths": {}, "components": {}}
    need = set()
    for p, m in KEEP:
        out["paths"].setdefault(p, {})[m] = copy.deepcopy(spec["paths"][p][m]); refs(out["paths"][p][m], need)
    seen = set()
    while need:
        r = need.pop()
        if r in seen: continue
        seen.add(r)
        _, _, kind, name = r.split("/")
        node = spec["components"][kind][name]
        out["components"].setdefault(kind, {})[name] = node
        n2 = set(); refs(node, n2); need |= n2 - seen
    return out
if __name__ == "__main__":
    s = json.load(open(sys.argv[1], encoding="utf-8")); o = slice_spec(s)  # noqa: SIM115
    json.dump(o, open(sys.argv[2], "w", encoding="utf-8")); print(sys.argv[1], "paths", len(s["paths"]), "slice schemas", len(o["components"].get("schemas", {})), "bytes", len(json.dumps(o)), "ver", s["info"].get("version"))  # noqa: SIM115
