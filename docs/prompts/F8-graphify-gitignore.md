# F8: Stop tracking generated graph history (housekeeping)

No code change. No AC (repo hygiene). Merge it on its own PR.

## Problem

`graphify-out/` has 295 tracked files (~5 MB): two dated snapshot folders (`2026-10-15/`, `2026-10-16/`), 273 cache files under `graphify-out/cache/`, and machine-local state files (`.graphify_python`, `.graphify_root`). Graph queries and updates dirty the checkout.

## Owns

- `.gitignore`
- the git index for `graphify-out/` (`git rm --cached` only; **never delete the files on disk**)

## Build

1. First open `.graphify_root`, `.graphify_python` and `cache/last_query_stamp` (if present) and record in the PR whether they contain absolute machine paths. Do not paste the paths themselves.
2. Keep tracked, because `AGENTS.md` tells agents to use them on a fresh clone: `graphify-out/graph.json`, `graphify-out/GRAPH_REPORT.md`, `graphify-out/manifest.json`, `graphify-out/.graphify_labels.json`, `graphify-out/wiki/` if it exists.
3. Add to `.gitignore`:
   ```
   graphify-out/cache/
   graphify-out/20*/
   graphify-out/.graphify_python
   graphify-out/.graphify_root
   graphify-out/graph.html
   graphify-out/cost.json
   ```
   Check `graph.html` and `cost.json`: if any doc links to `graph.html`, keep it tracked and remove that line.
4. `git rm -r --cached` the now-ignored paths.
5. Verify: run `graphify query "registry"`, then `git status` shows no change.

## Done when

A fresh clone still has `graph.json` and `GRAPH_REPORT.md`; queries and `graphify update .` leave `git status` clean except for the kept files when the graph really changed.
