/* In-place product tour: a spotlight walks through the real page, one step at a time.
   Opens by itself on a page's first visit; the "Guide" button reopens it. No dependencies. */
(() => {
  const STEPS = {
    "/": [
      { title: "Welcome", text: "This is a self-healing tool registry. It sits between an AI agent and the APIs and MCP servers it calls. When an API changes shape, it repairs the call so the agent keeps working, without a new prompt or a redeploy." },
      { sel: "#hero-h", title: "The problem it solves", text: "APIs drift: a field is renamed, a type changes, a tool moves. A normal agent breaks on the next call. Here, the registry notices the break and patches the call in memory." },
      { sel: "section[aria-label='Animated flow diagram']", title: "How a heal works", text: "The agent's call fails. The registry reads the new API spec, diffs it against the old one, builds a fix from that evidence only, retries once and checks the result. No values are invented." },
      { sel: "section[aria-label='Benchmark results']", title: "Measured, not claimed", text: "These numbers come from the benchmark report. The Report tab shows the full run." },
      { sel: "header nav.tabs", title: "Where to go next", text: "Live stream runs two agents side by side. Patch log lists every heal. Connections adds your own MCP servers and APIs." },
      { sel: "header .btn.primary", title: "Try it", text: "Open the live demo. A short guide there shows how to break the API and watch it heal." },
    ],
    "/live": [
      { title: "The live demo", text: "Two agents do the same task against the same mock API. One calls it directly. The other goes through the self-healing registry. You break the API and compare." },
      { sel: "#mutations", title: "1. Break the API", text: "Each button is a real kind of API drift: a renamed field, a changed type, a wrapped response, a new required value. Click one; if no run is going, a quick run starts so the break is actually hit." },
      { sel: "#start-scripted", title: "2. Or start a run first", text: "A scripted run makes the same tool calls every time, with no LLM cost. Start it, then break the API mid-run to see a live heal." },
      { sel: "#col-baseline", title: "Without healing", text: "The baseline agent sees the raw error and its task fails or goes off track." },
      { sel: "#col-healing", title: "With healing", text: "The same call fails here too, but the registry detects the drift, patches the call and the agent gets a normal answer." },
      { sel: "#mutation-chip", title: "What is broken right now", text: "The active drift. Use Clear mutation or Reset to go back to the original API." },
      { sel: "[data-tab='heals']", tab: "heals", title: "3. The patch log", text: "Every heal attempt writes exactly one row: what broke, how it was fixed, how long it took. Refusals are logged too." },
      { sel: "#view-heals", tab: "heals", title: "See what changed", text: "Click a row to open it. An animation shows each change the fix made, for example the API now nesting a field under data and the registry moving it back where the agent expects it." },
      { sel: "[data-tab='metrics']", tab: "metrics", title: "4. Metrics", text: "Recovered heals, safe refusals and time to recover, split by tier: tier 1 builds a fix, tier 0 reuses a stored one instantly." },
      { title: "That's it", tab: "live", text: "Reopen this guide any time with the Guide button in the corner." },
    ],
    "/connections": [
      { title: "Connections", text: "Add the MCP servers and APIs the gateway should call and heal. Saved entries load the next time the gateway starts." },
      { sel: "#servers", title: "MCP servers", text: "Servers from config/mcp_servers.json. Ones started by a local command are file-only and read-only here, for safety." },
      { sel: "#apis", title: "Other APIs", text: "Non-MCP APIs: OpenAPI 3, Swagger 2.0 or GraphQL. They are healed the same way." },
      { sel: "#type", title: "1. Pick the kind", text: "An MCP server over HTTP, or an API described by an OpenAPI, Swagger or GraphQL spec." },
      { sel: "#url", title: "2. Where it lives", text: "For MCP, the server's endpoint URL. For an API, its base URL. Only http and https are accepted." },
      { sel: "#token", title: "3. Credentials, safely", text: "Type the NAME of an environment variable that holds the token, for example BILLING_TOKEN. The token itself never goes into this page or the config file." },
      { sel: "#test", title: "4. Test, then save", text: "Test connection connects once and lists the tools it found. Save writes the entry. Tools appear as name__tool." },
    ],
  };

  const page = STEPS[location.pathname] || [];
  if (!page.length) return;
  const KEY = "guide-seen:" + location.pathname;
  const store = {
    get() { try { return localStorage.getItem(KEY); } catch (e) { return null; } },
    set() { try { localStorage.setItem(KEY, "1"); } catch (e) { /* private mode: show again next time */ } },
  };

  const css = document.createElement("style");
  css.textContent = `
  .g-launch { position: fixed; right: 18px; bottom: 18px; z-index: 60; display: inline-flex; align-items: center; gap: 7px; padding: 8px 14px; border-radius: 999px; border: 1px solid var(--line-2, #b9c6b3); background: var(--panel, #fff); box-shadow: 0 4px 16px rgba(0,0,0,.08); font: 500 13.5px var(--sans, sans-serif); }
  .g-launch b { display: inline-grid; place-items: center; width: 18px; height: 18px; border-radius: 50%; background: var(--ink, #000); color: var(--on-ink, #fff); font-size: 11px; }
  .g-shade { position: fixed; inset: 0; z-index: 70; }
  .g-spot { position: fixed; z-index: 71; border-radius: 12px; pointer-events: none; box-shadow: 0 0 0 9999px rgba(10,14,8,.55); transition: all .38s cubic-bezier(.2,.8,.2,1); }
  .g-spot::after { content: ""; position: absolute; inset: -4px; border-radius: 14px; border: 2px solid var(--accent, #19e76e); animation: g-pulse 1.6s ease-out infinite; }
  .g-spot.center { left: 50% !important; top: 42% !important; width: 0 !important; height: 0 !important; }
  .g-spot.center::after { display: none; }
  @keyframes g-pulse { 0% { opacity: .9; transform: scale(1); } 100% { opacity: 0; transform: scale(1.06); } }
  .g-card { position: fixed; z-index: 72; width: min(360px, calc(100vw - 32px)); background: var(--panel, #fff); color: var(--ink, #000); border: 1px solid var(--line-2, #b9c6b3); border-radius: 14px; padding: 16px 18px 14px; box-shadow: 0 18px 50px rgba(0,0,0,.22); transition: left .38s cubic-bezier(.2,.8,.2,1), top .38s cubic-bezier(.2,.8,.2,1), opacity .2s; }
  .g-card small { font: 11px var(--mono, monospace); letter-spacing: .06em; color: var(--muted, #7d8778); text-transform: uppercase; }
  .g-card h3 { margin: 4px 0 6px; font-size: 17px; }
  .g-card p { margin: 0 0 14px; color: var(--ink-2, #3b4237); font-size: 14px; line-height: 1.5; }
  .g-row { display: flex; align-items: center; gap: 8px; }
  .g-dots { display: flex; gap: 5px; flex: 1; }
  .g-dots i { width: 6px; height: 6px; border-radius: 50%; background: var(--line-2, #b9c6b3); transition: all .25s; }
  .g-dots i.on { width: 18px; border-radius: 3px; background: var(--ink, #000); }
  .g-card button { border-radius: 8px; padding: 6px 12px; border: 1px solid var(--line-2, #b9c6b3); background: var(--panel, #fff); font-size: 13.5px; }
  .g-card button.next { background: var(--ink, #000); color: var(--on-ink, #fff); border-color: var(--ink, #000); }
  .g-card button.skip { border: 0; background: none; color: var(--muted, #7d8778); padding: 6px 4px; }
  .g-in { animation: g-in .3s ease-out; }
  @keyframes g-in { from { opacity: 0; transform: translateY(6px); } }
  @media (prefers-reduced-motion: reduce) { .g-spot, .g-card { transition: none; } .g-spot::after, .g-in { animation: none; } }`;
  document.head.appendChild(css);

  const launch = document.createElement("button");
  launch.className = "g-launch";
  launch.type = "button";
  launch.setAttribute("aria-label", "Open the guide");
  launch.innerHTML = "<b>?</b>Guide";
  document.body.appendChild(launch);

  let i = 0, shade, spot, card;
  const visible = (s) => {
    if (!s.sel) return true;
    const n = document.querySelector(s.sel);
    return n && n.getClientRects().length > 0;
  };
  function openTab(name) {
    const b = document.querySelector(`[data-tab='${name}']`);
    if (b && b.getAttribute("aria-selected") !== "true") b.click();
  }
  function place() {
    const s = page[i];
    const n = s.sel && document.querySelector(s.sel);
    const pad = 8, gap = 14;
    const cw = card.offsetWidth, ch = card.offsetHeight;
    if (!n) {
      spot.classList.add("center");
      card.style.left = Math.max(16, (innerWidth - cw) / 2) + "px";
      card.style.top = Math.max(16, innerHeight * 0.42 - ch / 2) + "px";
      return;
    }
    spot.classList.remove("center");
    const r = n.getBoundingClientRect();
    Object.assign(spot.style, { left: r.left - pad + "px", top: r.top - pad + "px", width: r.width + pad * 2 + "px", height: r.height + pad * 2 + "px" });
    let top = r.bottom + pad + gap;
    let left = Math.min(innerWidth - cw - 16, Math.max(16, r.left + r.width / 2 - cw / 2));
    if (top + ch > innerHeight - 12) top = r.top - pad - gap - ch;
    if (top < 12) {
      // A big target: sit beside it if there is room, else pin to the bottom corner.
      top = Math.min(innerHeight - ch - 16, Math.max(16, r.top));
      if (innerWidth - r.right > cw + 32) left = r.right + pad + gap;
      else if (r.left > cw + 32) left = r.left - pad - gap - cw;
      else { top = innerHeight - ch - 16; left = innerWidth - cw - 16; }
    }
    card.style.left = left + "px";
    card.style.top = top + "px";
  }
  function show(next) {
    const dir = next >= i ? 1 : -1;
    let k = next;
    for (; k >= 0 && k < page.length; k += dir) {
      if (page[k].tab) openTab(page[k].tab);
      if (visible(page[k])) break; // a step whose target is not on screen is skipped
    }
    if (k < 0 || k >= page.length) return close();
    i = k;
    const s = page[i];
    const n = s.sel && document.querySelector(s.sel);
    if (n) n.scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    card.replaceChildren();
    const meta = document.createElement("small");
    meta.textContent = `Step ${i + 1} of ${page.length}`;
    const h = document.createElement("h3");
    h.textContent = s.title;
    const p = document.createElement("p");
    p.textContent = s.text;
    const row = document.createElement("div");
    row.className = "g-row";
    const dots = document.createElement("div");
    dots.className = "g-dots";
    page.forEach((_, j) => { const d = document.createElement("i"); if (j === i) d.className = "on"; dots.appendChild(d); });
    const btn = (label, cls, fn) => { const b = document.createElement("button"); b.type = "button"; b.textContent = label; b.className = cls; b.onclick = fn; return b; };
    row.append(dots, btn("Skip", "skip", close));
    if (i > 0) row.append(btn("Back", "", () => show(i - 1)));
    const last = i === page.length - 1;
    const nb = btn(last ? "Done" : "Next", "next", () => (last ? close() : show(i + 1)));
    row.append(nb);
    card.append(meta, h, p, row);
    card.classList.remove("g-in"); void card.offsetWidth; card.classList.add("g-in");
    place();
    setTimeout(place, 420); // after smooth scrolling settles
    nb.focus({ preventScroll: true });
  }
  function onKey(e) {
    if (e.key === "Escape") close();
    else if (e.key === "ArrowRight") show(i + 1);
    else if (e.key === "ArrowLeft" && i > 0) show(i - 1);
  }
  function open() {
    if (card) return;
    shade = document.createElement("div"); shade.className = "g-shade";
    spot = document.createElement("div"); spot.className = "g-spot center";
    card = document.createElement("div"); card.className = "g-card";
    card.setAttribute("role", "dialog"); card.setAttribute("aria-label", "Guide");
    shade.onclick = close;
    document.body.append(shade, spot, card);
    addEventListener("resize", place); addEventListener("scroll", place, true); addEventListener("keydown", onKey);
    show(0);
  }
  function close() {
    store.set();
    [shade, spot, card].forEach((n) => n && n.remove());
    shade = spot = card = null;
    removeEventListener("resize", place); removeEventListener("scroll", place, true); removeEventListener("keydown", onKey);
    launch.focus({ preventScroll: true });
  }
  launch.onclick = open;
  if (!store.get()) setTimeout(open, 700);
})();
