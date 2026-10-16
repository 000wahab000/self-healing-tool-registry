/* In-place product tour: a spotlight walks through the real page, one step at a time.
   Opens by itself on a page's first visit; the "Guide" button reopens it. No dependencies. */
(() => {
  // Plain words for a first-time, non-technical visitor. One idea per step.
  // One tour through the whole app, in plain words for a first-time, non-technical visitor.
  // Each step names its page; the tour opens the next page itself and carries on there.
  const at = (page, list) => list.map((st) => ({ ...st, page }));
  const TOUR = [
    ...at("/", [

      { title: "Welcome", text: "AI assistants get work done by calling other services, like a booking system or a customer database. This tool keeps those calls working when the services change." },
      { sel: "#hero-h", title: "The problem", text: "Services change over time: a box gets renamed, a number becomes text. An assistant that still sends the old form simply fails. This tool notices and fixes the call for it." },
      { sel: "section[aria-label='Animated flow diagram']", title: "How it fixes things", text: "When a call fails, it checks what the service now expects, adjusts the call using only what the assistant already sent, tries once more and checks the answer. It never makes up information." },
      { sel: "section[aria-label='Benchmark results']", title: "Real results", text: "These numbers come from real test runs, not promises. The Report page has the details." },
      { sel: "header nav.tabs", title: "Find your way", text: "Live stream is the hands-on demo. Patch log lists every fix. Connections is where you add your own services." },
      { sel: "header .btn.primary", title: "Next: the live demo", text: "Press Next and the tour opens the live demo for you." },
    ]),
    ...at("/live", [
      { title: "The live demo", text: "Two assistants do the same job. The one on the left talks to the service directly. The one on the right goes through this tool. You will break the service and compare." },
      { sel: "#prompt", title: "1. What you ask", text: "This is the request both assistants receive. You can change it to anything you like and press Send prompt. Nothing else on the page changes." },
      { sel: "#acts", title: "Or pick a ready-made story", text: "Each card is a short scenario. Clicking one fills in the request and runs both assistants for you." },
      { sel: "#mutations", title: "2. Break the service", text: "Each button changes the service in a realistic way, like renaming a field. Click one; the assistants run, and you watch what happens." },
      { sel: "#col-baseline", title: "Without this tool", text: "Watch for a red shake and \"broke here\": that is the exact step where the service rejected the assistant." },
      { sel: "#col-healing", title: "With this tool", text: "The same step breaks here too, then turns green: \"broke here, healed\". The assistant never had to deal with the error." },
      { sel: "#cost", title: "3. Why it matters", text: "After each run, this chart compares the two. Every error costs the plain assistant extra work, extra AI time and money. Here you see the difference." },
      { sel: "[data-tab='heals']", tab: "heals", title: "4. The fix list", text: "Every fix is written down here: what broke, what was changed and how long it took. Click a row to see the change animated." },
      { sel: "[data-tab='metrics']", tab: "metrics", title: "5. The scoreboard", text: "Totals across every run: how many breaks were fixed, how many were safely refused, and how fast fixes happened." },
      { sel: "[data-tab='mcp']", tab: "mcp", title: "6. Plug in any AI app", text: "Apps like Claude Desktop or Cursor connect here once. Every tool they use then gets the same protection." },
      { sel: "[data-tab='report']", tab: "report", title: "7. The full report", text: "The measured test results behind every number on these pages." },
      { sel: "header nav.tabs a[href='/connections'], header nav.tabs [href='/connections']", title: "Next: your own services", text: "Press Next to see where you add the services your assistant uses." },
    ]),
    ...at("/connections", [

      { title: "Your services", text: "Here you tell the tool which services your assistant uses, so it can protect those calls too." },
      { sel: "#servers", title: "Connected services", text: "Services the tool already knows. Ones marked 'configured in file' were set up by an administrator." },
      { sel: "#type", title: "1. What kind of service", text: "If your service speaks MCP (an AI tool standard), pick that. Most other web services publish an OpenAPI or Swagger description; pick the one your provider names." },
      { sel: "#url", title: "2. Its web address", text: "Paste the address your provider gave you. It starts with https://" },
      { sel: "#token", title: "3. Keep passwords out", text: "Never paste a password or key here. Type only the name your administrator stored it under, like BILLING_TOKEN." },
      { sel: "#test", title: "4. Check it, then save", text: "Test connection shows the actions the service offers. If that looks right, press Save." },
      { title: "You're ready", text: "That is the whole app. Press Tour at the top any time to see it again, or Play to let it run by itself." },
    ]),
  ];
  const here = location.pathname;
  if (!TOUR.some((st) => st.page === here)) return;
  const ss = {  // tour position for this browser tab; a blocked storage just ends the tour at the page edge
    get(k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { if (v === null) sessionStorage.removeItem(k); else sessionStorage.setItem(k, v); } catch (e) { /* ignore */ } },
  };
  const seen = {
    get() { try { return localStorage.getItem("guide-seen"); } catch (e) { return null; } },
    set() { try { localStorage.setItem("guide-seen", "1"); } catch (e) { /* show again next time */ } },
  };

  const css = document.createElement("style");
  css.textContent = `
  .g-launch { position: fixed; right: 16px; bottom: 16px; z-index: 60; height: 36px; padding: 0 16px; border-radius: var(--r-sm); border: 1px solid var(--line-2); background: var(--panel); color: var(--ink); font: 500 var(--fs-base)/var(--lh-sm) var(--sans); box-shadow: var(--shadow-float); }
  .g-launch:hover { background: var(--soft); }
  .g-launch.in-bar { position: static; box-shadow: none; height: 32px; padding: 0 12px; font-size: var(--fs-sm); }
  .g-shade { position: fixed; inset: 0; z-index: 70; }
  .g-spot { position: fixed; z-index: 71; border-radius: var(--r-lg); pointer-events: none; box-shadow: 0 0 0 9999px var(--scrim); outline: 2px solid var(--accent); transition: all .38s cubic-bezier(.2,.8,.2,1); }
  .g-spot.center { left: 50% !important; top: 42% !important; width: 0 !important; height: 0 !important; outline: 0; }
  .g-card { position: fixed; z-index: 72; width: min(420px, calc(100vw - 32px)); background: var(--panel); color: var(--ink); border: 1px solid var(--accent); border-radius: var(--r-lg); padding: 24px; box-shadow: var(--shadow-float); transition: left .38s cubic-bezier(.2,.8,.2,1), top .38s cubic-bezier(.2,.8,.2,1); }
  .g-card small { font: 500 var(--fs-xs)/var(--lh-xs) var(--sans); letter-spacing: .04em; text-transform: uppercase; color: var(--ink-2); }
  .g-card h3 { margin: 8px 0 12px; font: 600 var(--fs-lg)/var(--lh-lg) var(--sans); letter-spacing: -.01em; }
  .g-card p { margin: 0 0 16px; color: var(--ink-2); font-size: var(--fs-base); line-height: var(--lh-base); }
  .g-row { display: flex; gap: 10px; flex-wrap: wrap; }
  .g-card button { height: 36px; border-radius: var(--r-sm); padding: 0 16px; border: 1px solid var(--line-2); background: var(--panel); color: var(--ink); font: 500 var(--fs-base)/var(--lh-sm) var(--sans); }
  .g-card button:hover { background: var(--soft); }
  .g-card button.next { background: var(--ink); color: var(--on-ink); border-color: var(--ink); }
  .g-card button.next:hover { background: var(--ink); opacity: .88; }
  .g-card button.play[aria-pressed="true"] { border-color: var(--accent-ink); color: var(--accent-ink); }
  .g-bar { height: 3px; background: var(--soft); border-radius: 2px; margin: 0 0 14px; overflow: hidden; }
  .g-bar i { display: block; height: 100%; width: 0; background: var(--accent-ink); }
  .g-in { animation: g-in .3s ease-out; }
  @keyframes g-in { from { opacity: 0; transform: translateY(6px); } }
  @media (prefers-reduced-motion: reduce) { .g-spot, .g-card { transition: none; } .g-in { animation: none; } }`;
  document.head.appendChild(css);

  const launch = document.createElement("button");
  launch.className = "g-launch";
  launch.type = "button";
  launch.setAttribute("aria-label", "Start the guided tour");
  launch.textContent = "Tour";
  // In the top bar when the page has one (next to the views), else a floating button.
  const bar = document.querySelector("header .top-in nav.tabs");
  if (bar) { launch.classList.add("in-bar"); bar.after(launch); } else document.body.appendChild(launch);

  let i = 0, shade, spot, card, timer = null;
  let auto = ss.get("tour-auto") === "1";
  const visible = (st) => {
    if (!st.sel) return true;
    const n = document.querySelector(st.sel);
    return n && n.getClientRects().length > 0;
  };
  function openTab(name) {
    const b = document.querySelector(`[data-tab='${name}']`);
    if (b && b.getAttribute("aria-pressed") !== "true" && b.getAttribute("aria-selected") !== "true") b.click();
  }
  function place() {
    if (!card) return;
    const st = TOUR[i];
    const n = st.sel && document.querySelector(st.sel);
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
  function go(k) {
    clearTimeout(timer);
    if (k < 0) k = 0;
    if (k >= TOUR.length) return close();
    if (TOUR[k].page !== here) {  // the next step lives on another page: open it, the tour resumes there
      ss.set("tour-step", String(k));
      location.href = TOUR[k].page;
      return;
    }
    show(k, k >= i ? 1 : -1);
  }
  function show(k, dir) {
    for (; k >= 0 && k < TOUR.length && TOUR[k].page === here; k += dir) {
      if (TOUR[k].tab) openTab(TOUR[k].tab);
      if (visible(TOUR[k])) break; // a step whose target is not on screen is skipped
    }
    if (k < 0) k = 0;
    if (k >= TOUR.length) return close();
    if (TOUR[k].page !== here) return go(k);
    i = k;
    ss.set("tour-step", String(i));
    const st = TOUR[i];
    const n = st.sel && document.querySelector(st.sel);
    if (n) n.scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    card.replaceChildren();
    const meta = document.createElement("small");
    meta.textContent = `Step ${i + 1} of ${TOUR.length}`;
    const h = document.createElement("h3");
    h.textContent = st.title;
    const p = document.createElement("p");
    p.textContent = st.text;
    const bar = document.createElement("div");
    bar.className = "g-bar";
    const fill = document.createElement("i");
    bar.append(fill);
    const row = document.createElement("div");
    row.className = "g-row";
    const btn = (label, cls, fn) => { const b = document.createElement("button"); b.type = "button"; b.textContent = label; b.className = cls; b.onclick = fn; return b; };
    if (i > 0) row.append(btn("Back", "", () => { auto = false; ss.set("tour-auto", null); go(i - 1); }));
    const last = i === TOUR.length - 1;
    const nb = btn(last ? "Done" : "Next", "next", () => go(i + 1));
    const play = btn(auto ? "Pause" : "Play", "play", () => {
      auto = !auto;
      ss.set("tour-auto", auto ? "1" : null);
      show(i, 1);
    });
    play.setAttribute("aria-pressed", String(auto));
    row.append(nb, play, btn("Skip tour", "", close));
    card.append(meta, h, p, bar, row);
    card.classList.remove("g-in"); void card.offsetWidth; card.classList.add("g-in");
    place();
    setTimeout(place, 420); // after smooth scrolling settles
    nb.focus({ preventScroll: true });
    clearTimeout(timer);
    if (auto && !last) {
      // Reading time: a base plus a little per word, so long steps get longer.
      const ms = 3500 + st.text.split(" ").length * 230;
      fill.style.transition = `width ${ms}ms linear`;
      requestAnimationFrame(() => requestAnimationFrame(() => { fill.style.width = "100%"; }));
      timer = setTimeout(() => go(i + 1), ms);
    }
  }
  function onKey(e) {
    if (e.key === "Escape") close();
    else if (e.key === "ArrowRight") go(i + 1);
    else if (e.key === "ArrowLeft" && i > 0) go(i - 1);
  }
  function open(k) {
    if (card) return;
    shade = document.createElement("div"); shade.className = "g-shade";
    spot = document.createElement("div"); spot.className = "g-spot center";
    card = document.createElement("div"); card.className = "g-card";
    card.setAttribute("role", "dialog"); card.setAttribute("aria-label", "Guided tour");
    shade.onclick = close;
    document.body.append(shade, spot, card);
    addEventListener("resize", place); addEventListener("scroll", place, true); addEventListener("keydown", onKey);
    show(k, 1);
  }
  function close() {
    clearTimeout(timer);
    seen.set();
    ss.set("tour-step", null);
    ss.set("tour-auto", null);
    auto = false;
    [shade, spot, card].forEach((n) => n && n.remove());
    shade = spot = card = null;
    removeEventListener("resize", place); removeEventListener("scroll", place, true); removeEventListener("keydown", onKey);
    launch.focus({ preventScroll: true });
  }
  // The Tour button always starts the whole tour from the first step.
  launch.onclick = () => (here === TOUR[0].page ? open(0) : go(0));
  const resume = ss.get("tour-step");
  if (resume !== null && TOUR[+resume] && TOUR[+resume].page === here) setTimeout(() => open(+resume), 500);
  else if (!seen.get() && here === TOUR[0].page) setTimeout(() => open(0), 700);
})();
