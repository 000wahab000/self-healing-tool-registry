"""Time healer.openapi_loader.resolve_refs/operations on a Stripe slice (no network, no LLM)."""
import faulthandler
import json
import sys
import time
from pathlib import Path

from healer import openapi_loader as L

p = Path(sys.argv[1])
spec = json.loads(p.read_text(encoding="utf-8"))
print("slice schemas:", len(spec["components"]["schemas"]), "bytes:", p.stat().st_size, flush=True)
faulthandler.dump_traceback_later(int(sys.argv[2]) if len(sys.argv) > 2 else 40, exit=True)
t = time.time()
resolved = L.resolve_refs(spec)
print("resolve_refs ok in", round(time.time() - t, 2), "s; resolved json bytes:", len(json.dumps(resolved)), flush=True)
t = time.time()
ops = L.operations(resolved)
print("operations ok in", round(time.time() - t, 2), "s:", list(ops), flush=True)
