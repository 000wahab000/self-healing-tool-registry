/* In-place product tour: a spotlight walks through the real page, one step at a time.
   Opens by itself on a page's first visit; the "Guide" button reopens it. No dependencies. */
(() => {
  // Plain words for a first-time, non-technical visitor. One idea per step.
  const STEPS = {
    "/": [
      { title: "Welcome", text: "AI assistants get work done by calling other services, like a booking system or a customer database. This tool keeps those calls working when the services change." },
      { sel: "#hero-h", title: "The problem", text: "Services change over time: a box gets renamed, a number becomes text. An assistant that still sends the old form simply fails. This tool notices and fixes the call for it." },
      { sel: "section[aria-label='Animated flow diagram']", title: "How it fixes things", text: "When a call fails, it checks what the service now expects, adjusts the call using only what the assistant already sent, tries once more and checks the answer. It never makes up information." },
      { sel: "section[aria-label='Benchmark results']", title: "Real results", text: "These numbers come from real test runs, not promises. The Report page has the details." },
      { sel: "header nav.tabs", title: "Find your way", text: "Live stream is the hands-on demo. Patch log lists every fix. Connections is where you add your own services." },
      { sel: "header .btn.primary", title: "Try it yourself", text: "Open the live demo. A short tour there shows you what to click." },
    ],
    "/live": [
      { title: "The live demo", text: "Two assistants do the same job. The one on the left talks to the service directly. The one on the right goes through this tool. You will break the service and compare." },
      { sel: "#prompt", title: "1. What you ask", text: "This is the request both assistants receive. You can change it to anything you like and press Send prompt. Nothing else on the page changes." },
      { sel: "#acts", title: "Or pick a ready-made story", text: "Each card is a short scenario. Clicking one fills in the request and runs both assistants for you." },
      { sel: "#mutations", title: "2. Break the service", text: "Each button changes the service in a realistic way, like renaming a field. Click one; the assistants run, and you watch what happens." },
      { sel: "#col-baseline", title: "Without this tool", text: "Watch for a red shake and \"broke here\": that is the exact step where the service rejected the assistant." },
      { sel: "#col-healing", title: "With this tool", text: "The same step breaks here too, then turns green: \"broke here, healed\". The assistant never had to deal with the error." },
      { sel: "#cost", title: "3. Why it matters", text: "After each run, this chart compares the two. Every error costs the plain assistant extra work, extra AI time and money. Here you see the difference." },
      { sel: "[data-tab='heals']", tab: "heals", title: "4. The fix list", text: "Every fix is written down here: what broke, what was changed and how long it took. Click a row to see the change animated." },
      { title: "You're ready", tab: "live", text: "Press TOUR at the top any time to see this again." },
    ],
    "/connections": [
      { title: "Your services", text: "Here you tell the tool which services your assistant uses, so it can protect those calls too." },
      { sel: "#servers", title: "Connected services", text: "Services the tool already knows. Ones marked 'configured in file' were set up by an administrator." },
      { sel: "#type", title: "1. What kind of service", text: "If your service speaks MCP (an AI tool standard), pick that. Most other web services publish an OpenAPI or Swagger description; pick the one your provider names." },
      { sel: "#url", title: "2. Its web address", text: "Paste the address your provider gave you. It starts with https://" },
      { sel: "#token", title: "3. Keep passwords out", text: "Never paste a password or key here. Type only the name your administrator stored it under, like BILLING_TOKEN." },
      { sel: "#test", title: "4. Check it, then save", text: "Test connection shows the actions the service offers. If that looks right, press Save." },
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
  .g-launch { position: fixed; right: 18px; bottom: 18px; z-index: 60; padding: 8px 16px; border-radius: 4px; border: 1px solid var(--ink, #000); background: var(--panel, #fff); font: 500 12.5px var(--mono, monospace); letter-spacing: .12em; text-transform: uppercase; box-shadow: 0 4px 16px rgba(0,0,0,.08); }
  .g-launch.in-bar { position: static; box-shadow: none; padding: 5px 12px; }
  .g-shade { position: fixed; inset: 0; z-index: 70; }
  .g-spot { position: fixed; z-index: 71; border-radius: 10px; pointer-events: none; box-shadow: 0 0 0 9999px rgba(10,14,8,.6); outline: 2px solid #fff; transition: all .38s cubic-bezier(.2,.8,.2,1); }
  .g-spot.center { left: 50% !important; top: 42% !important; width: 0 !important; height: 0 !important; outline: 0; }
  .g-card { position: fixed; z-index: 72; width: min(420px, calc(100vw - 32px)); background: var(--panel, #fff); color: var(--ink, #000); border: 2px solid #1d4ed8; border-radius: 6px; padding: 20px 22px 18px; box-shadow: 0 20px 60px rgba(0,0,0,.3); transition: left .38s cubic-bezier(.2,.8,.2,1), top .38s cubic-bezier(.2,.8,.2,1); }
  .g-card small { font: 14px var(--serif, Georgia, serif); letter-spacing: .14em; text-transform: uppercase; color: var(--ink-2, #3b4237); }
  .g-card h3 { margin: 6px 0 10px; font: 400 28px/1.1 var(--serif, Georgia, serif); letter-spacing: .03em; text-transform: uppercase; }
  .g-card p { margin: 0 0 18px; color: var(--ink-2, #3b4237); font-size: 15.5px; line-height: 1.55; }
  .g-row { display: flex; gap: 10px; flex-wrap: wrap; }
  .g-card button { border-radius: 4px; padding: 10px 18px; border: 1px solid var(--ink, #000); background: var(--panel, #fff); font: 500 13px var(--mono, monospace); letter-spacing: .12em; text-transform: uppercase; }
  .g-card button.next { background: var(--ink, #000); color: var(--on-ink, #fff); }
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
    const btn = (label, cls, fn) => { const b = document.createElement("button"); b.type = "button"; b.textContent = label; b.className = cls; b.onclick = fn; return b; };
    if (i > 0) row.append(btn("Back", "", () => show(i - 1)));
    const last = i === page.length - 1;
    const nb = btn(last ? "Done" : "Next", "next", () => (last ? close() : show(i + 1)));
    row.append(nb, btn("Skip tour", "", close));
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
