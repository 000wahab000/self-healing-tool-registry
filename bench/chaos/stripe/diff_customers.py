import json
import sys


def load(p): return json.load(open(p, encoding="utf-8"))
def resolve(spec, node):
    if isinstance(node, dict) and "$ref" in node:
        t = spec
        for part in node["$ref"][2:].split("/"): t = t[part]
        return t
    return node
def facts(spec):
    out = {}
    for (p, m) in [("/v1/customers","get"),("/v1/customers","post"),("/v1/customers/{customer}","get")]:
        op = spec["paths"][p][m]
        params = {x["name"]+":"+x["in"]: (x.get("required", False), json.dumps(resolve(spec, x.get("schema", {})).get("type"))) for x in [resolve(spec, q) for q in op.get("parameters", [])]}
        body = {}
        rb = op.get("requestBody", {}).get("content", {}).get("application/x-www-form-urlencoded", {}).get("schema", {})
        rb = resolve(spec, rb)
        for k, v in rb.get("properties", {}).items():
            v = resolve(spec, v); body[k] = v.get("type") or ("anyOf" if "anyOf" in v else "?")
        out[p+" "+m] = {"params": params, "body": body, "required_body": rb.get("required", [])}
    return out
a, b = facts(load(sys.argv[1])), facts(load(sys.argv[2]))
for k in a:
    pa, pb = a[k]["params"], b[k]["params"]
    print(k, "params -", sorted(set(pa)-set(pb)), "+", sorted(set(pb)-set(pa)), "changed", [x for x in pa if x in pb and pa[x]!=pb[x]])
    ba, bb = a[k]["body"], b[k]["body"]
    print("   body -", sorted(set(ba)-set(bb)), "+", sorted(set(bb)-set(ba)), "type changes", [(x,ba[x],bb[x]) for x in ba if x in bb and ba[x]!=bb[x]], "req", a[k]["required_body"], "->", b[k]["required_body"])
