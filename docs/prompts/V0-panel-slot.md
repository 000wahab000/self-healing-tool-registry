# V0: A plug-in slot for dashboard panels (foundation for V1-V3)

## Why

`dashboard/index.html` is one ~1550-line file with inline JS. Every new view means editing the middle of it, and it also contains an **offline demo stub** (around line 672: `if (path.startsWith("/api/state")) return Promise.resolve(state(...))`) that fakes the API when no server is running. V1-V3 add metric panels. This task builds the slot they plug into, so each panel is its own file and never touches the others.

## Owns

- `dashboard/panels/registry.js` (new)
- `dashboard/panels/README.md` (new, ~15 lines: how to add a panel)
- `dashboard/index.html`: one container element + one `<script>` include + one call per poll. Nothing else.
- `dashboard/app.py`: serve `dashboard/panels/` as static files only if it is not already served (check how `ui.js` and `theme.css` are served and do the same)
- `tests/dashboard/test_ac_77_panel_slot.py` (new)
- `product.md`: one AC row

## Build

`registry.js` (plain JS, no build step, no framework, no new dependency):

```js
// Each panel: { id, title, endpoint|null, render(el, data, state) }
window.HealerPanels = {
  register(panel) {...},     // ignores duplicate ids
  mountAll(container) {...}, // creates one <section class="card pad" data-panel=id> per panel
  async refresh(state) {...} // per panel: fetch endpoint (if any) via the page's existing call() helper, then render; one panel throwing must not break the others (try/catch per panel, show a small error line)
};
```

- Panels load from `<script src="panels/<name>.js">` tags placed after `registry.js`. A missing file must not break the page.
- Hook `HealerPanels.refresh(state)` into the existing `poll()` after it renders, but throttle endpoint fetches to at most once every 5 s (state is passed every poll, so polling cost stays the same).
- Offline demo: if the page is in offline or stub mode, `refresh` must route endpoint fetches through the same stub function the page already uses. Unknown endpoints resolve to `null`, and panels render "No data offline".
- Reuse existing CSS classes from `theme.css` (`card`, `pad`, `muted`). No new colours.

## Room for later

Adding a panel = one new file + one `<script>` tag. V1, V2 and V3 each do exactly that.

## Tests (`test_ac_77_*`)

- `GET /panels/registry.js` returns 200 with a JS content type.
- `index.html` contains the panel container and the registry script tag.
- If the repo has browser tests (`tests/e2e/`), add one: the page loads with zero registered panels and no console errors. Otherwise state in the PR that the browser check was done by hand.

## Done when

An empty registry changes nothing visible, and a test panel file renders a card without editing `index.html` again.
