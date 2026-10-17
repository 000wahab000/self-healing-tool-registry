# GitHub MCP chaos test

Date: 2026-10-17. Question: when an agent holds a false tool schema, does the registry translate its calls correctly to the real GitHub MCP server, refuse safely, or send something wrong?

## Setup

```
small agent (claude -p, Haiku, one MCP connection) -> healer MCP (port 8097)
  -> shim (port 8099) -> GitHub MCP (live: https://api.githubcopilot.com/mcp/ ; offline: fake_upstream.py)
```

1. The shim serves a **false** `inputSchema` (profile from `profiles.py`) while the healer starts, so the healer freezes the false schema as the agent's tool schema.
2. The shim switches to plain passthrough. Every call made with the false schema now hits the real tool schema.
3. **Control** phase: 6 direct calls per profile (python MCP client, false arg names, no LLM). **Agent** phase: Haiku does 2 tasks per profile using only the healer.
4. The oracle is the upstream: what GitHub (or the strict fake) received and accepted, from the shim log, compared with the intended real arguments.

Expected outcomes are in `cases.yaml` (sha256 prefix `c5e549dd73a34ca7`), written before the first run and never edited.

Live target: `someonedabberr-spec/Testt`, an empty sandbox repo on a separate account. Only read tools were exposed (`get_me`, `search_repositories`, `list_issues`, `get_issue`, `get_file_contents`, `list_commits`).

## Proof

| Path | Contents |
|---|---|
| `proof/offline/` | Final offline run after the fix: `results.jsonl` (one row per call), `shim_calls.jsonl`, `upstream_calls.jsonl`, `summary.md`, agent transcripts `agent_*.stream.jsonl` |
| `proof/live/` | Final live GitHub run after the fix: same files (no `upstream_calls.jsonl`; GitHub is the upstream) |
| `proof/live_prefix_results.jsonl` | Live run before the fix (shows the false patch) |
| `proof/offline_run.log`, `proof/live_run.log` | Console output of both final runs |

The logs were scanned for tokens and personal data before commit. The token was only read from an env var and never logged.

## Results after the fix

### Offline (strict fake GitHub)

| Profile | Control (6 calls) | Agent |
|---|---|---|
| identity | 6 pass-through | not run |
| rename_owner_repo | 2 pass-through, 4 refused | 2 refused |
| rename_issue_number | 1 healed, 5 pass-through | 1 healed, 1 pass-through |
| int_to_string | 2 healed, 4 pass-through | 1 healed, 1 pass-through |
| wrap_args | 2 healed, 1 pass-through, 3 refused | 1 healed, 1 refused |
| nest_repo | 4 healed, 2 pass-through | 2 healed |
| enum_case | 1 healed, 5 pass-through | 1 healed, 1 pass-through |
| enum_synonym | 1 refused (expected), 5 pass-through | 1 refused, 2 pass-through, 1 agent arg error |
| merge_owner_repo | 4 refused (expected), 2 pass-through | 2 refused (expected) |
| decoy_unused | 6 pass-through | not run |
| decoy_used | 6 refused (expected) | not run |

**False patches: 0. Crashes: 0.** Misses against expectations: only `rename_owner_repo` (4 control, 2 agent) and 3 partial `wrap_args` controls, all safe refusals.

### Live (real GitHub MCP)

| Measure | Result |
|---|---|
| Real false patches | **0** |
| Scorer "FALSE_PATCH" rows | 2, both `enum_case`, where no heal ran: GitHub accepts `open` as well as `OPEN`, so the call was valid. Scoring artifact |
| Heals that succeeded live | 1 (`nest_repo`, agent) |
| Refusals where a heal was expected | most rename, wrap and nest controls (see open failure 1) |
| Environment misses | `get_issue #1`, `README.md` and commits do not exist in the empty repo, so GitHub returns business errors. Counted as "missed" by the scorer; not registry failures |

## Before vs after the fix

| | Before (live) | After (live) | After (offline) |
|---|---|---|---|
| Real false patches | 1 (`wrap_args`: `state` filter silently dropped) | 0 | 0 |
| `nest_repo` heals | 0 (leftover `"repository": {}`) | 1 | 6 of 6 |
| `wrap_args` heals | 0 | 0 | 3 |

**The fix:**
- L2 `request_schema` now validates MCP calls against the tool's `inputSchema` (`src/healer/verify.py`). Before, it skipped every MCP call, so a lenient upstream (GitHub ignores unknown keys) accepted a partial patch.
- `move` removes wrappers it empties (`src/healer/ops.py`). A partial unwrap now fails L2 and is refused.

Regression tests:
- `tests/integration/test_verify_layers.py::test_mcp_partial_unwrap_fails_request_schema`
- `tests/integration/test_verify_layers.py::test_mcp_full_unwrap_drops_the_empty_wrapper_and_passes`
- `tests/unit/test_ops.py::test_move_removes_wrappers_it_empties_only`

## Open failures

| # | Failure | Where |
|---|---|---|
| 1 | Live heals mostly time out: `HEAL_DEADLINE_S = 3.5` is too short for a remote MCP (spec fetch, diagnosis and replay over the network) | `src/healer/settings.py` |
| 2 | Two same-typed fields renamed at once (`owner`, `repo`) are refused: `_evidence` pairs fields by a shared name token, so both claim `repo_owner` | `src/healer/candidates.py:85-111` |
| 3 | Live `E1 -32001` from the GitHub MCP is treated as transient, so no heal is tried | `src/healer/adapters/mcp_upstream.py` |
| 4 | `wrap_args` heals only when every wrapped field maps to the real schema; otherwise it is refused (safe, but no heal) | diagnosis |
| 5 | The scorer counts a valid case-insensitive enum as wrong (`enum_case`) | `bench/chaos/github/run.py` scoring |

## Limits

- One run per profile per mode, so these are counts, not rates.
- The offline fake is an approximation of GitHub's tool schemas. The live run is the ground truth.
- The sandbox repo is empty, so several read tools return business errors live.
- Not covered yet (see `docs/plans/chaos-test-plan.md`): Stripe, httpbin, Petstore, GraphQL, transport faults, gateway restarts.

## Re-running

Offline, control plus agent:

```bash
W="$(pwd -W)"; PYTHONPATH="$W/src;$W" ../../../.venv/Scripts/python.exe bench/chaos/github/run.py
```

Live, control only (needs `MCP_GITHUB_TOKEN` exported):

```bash
W="$(pwd -W)"; PYTHONPATH="$W/src;$W" ../../../.venv/Scripts/python.exe bench/chaos/github/run.py --live --no-agent --upstream-url https://api.githubcopilot.com/mcp/ --token-env MCP_GITHUB_TOKEN --owner <owner> --repo <repo> --issue 1
```
