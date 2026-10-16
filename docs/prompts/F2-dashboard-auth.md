# F2: Shared dashboard auth module, guarding write routes (security, must fix)

## Problem

`dashboard/app.py` exposes `POST /api/start`, `/api/mutation`, `/api/reset` and `/api/explore` with no auth. On a hosted dashboard with `NVIDIA_API_KEY` set, any visitor can start paid LLM runs or reset another visitor's demo. `dashboard/connections.py` has its own `is_remote()` that guesses "local" from the client IP, which a same-host reverse proxy defeats (task F3 fixes that file; this task builds the shared module it will use).

## Owns

- `dashboard/auth.py` (new)
- `dashboard/app.py`: add a dependency to the four write routes only
- `tests/dashboard/test_ac_71_auth.py` (new)
- `product.md`: one AC row
- `README.md` or `docs/`: one short paragraph on the two env vars

## Build

`dashboard/auth.py`:

```python
AUTH_MODE_ENV = "DASHBOARD_AUTH"     # "off" | "token"
TOKEN_ENV = "DASHBOARD_TOKEN"

def auth_mode() -> str: ...
def require_write(request: Request) -> None:  # FastAPI dependency
```

Rules:
- The mode comes **only** from `DASHBOARD_AUTH`, never from the client address.
- Default: `"token"` when `PORT` is set (a hosting platform), otherwise `"off"`, so `python -m dashboard` stays frictionless on a laptop.
- `"off"`: allow.
- `"token"`: require `Authorization: Bearer <DASHBOARD_TOKEN>`, compared with `hmac.compare_digest`. A missing `DASHBOARD_TOKEN` gives 403 with a clear message. A wrong or missing header gives 401.
- Any unknown mode value fails closed (treat it as `"token"`).
- Never log the token.

In `app.py`, add `dependencies=[Depends(require_write)]` to the four POST routes. Do not change their bodies. GET routes stay open.

Front end: if `index.html` calls these routes, add the header only when a token is present in `sessionStorage` (key `dashboardToken`), plus a minimal prompt on a 401. Keep this change under ~30 lines. If that is not possible without restructuring, leave the front end alone and note it in the PR.

## Room for later

Any new write route adds the same dependency. F3 reuses `require_write` for `/connections`.

## Tests (`test_ac_71_*`)

With FastAPI `TestClient` and `monkeypatch.setenv`:
- mode off: `POST /api/reset` gives 200
- mode token, no token configured: 403
- mode token, wrong header: 401; right header: 200
- `X-Forwarded-For` or client host has no effect on the outcome
- `PORT` set with `DASHBOARD_AUTH` unset gives token mode
- `GET /api/state` stays 200 in every mode

## Done when

No write route runs without passing `require_write`, and local development without env vars works unchanged.
