// Live safety and timing panel (AC-79)
(function () {
  function el(tag, content, attrs = {}) {
    const node = document.createElement(tag);
    if (content !== undefined && content !== null) {
      if (typeof content === "string" || typeof content === "number") {
        node.textContent = String(content);
      } else if (Array.isArray(content)) {
        node.append(...content);
      } else {
        node.append(content);
      }
    }
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") node.className = v;
      else if (k === "style") node.style.cssText = v;
      else node.setAttribute(k, v);
    }
    return node;
  }

  function statTile(title, value, unit, sub, valueColor) {
    const card = el("div", null, { class: "card metric" });
    const valEl = el("div", value, { class: "v" });
    if (valueColor) valEl.style.color = valueColor;
    if (unit) valEl.appendChild(el("em", unit));
    card.append(el("small", title), valEl);
    if (sub) card.appendChild(el("div", sub, { class: "s" }));
    return card;
  }

  window.HealerPanels.register({
    id: "live_safety",
    title: "Live Safety & Timings",
    endpoint: "/api/metrics/live",
    render(container, data) {
      container.replaceChildren();

      const head = el("div", [
        el("div", [
          el("p", "This session's heals · live metrics", { class: "eyebrow" }),
          el("h3", "Live Safety & Timings"),
        ]),
      ], { class: "head", style: "margin-bottom: 16px;" });
      container.appendChild(head);

      if (!data) {
        container.appendChild(el("p", "No live session data available offline.", { class: "muted" }));
        return;
      }

      const outcomes = data.outcomes || {};
      const recovered = outcomes.RECOVERED || 0;
      const refused = outcomes.REFUSED || outcomes.ABORTED || 0;
      const failed = (outcomes.VERIFY_FAILED || 0) + (outcomes.FAILED || 0);
      const total = recovered + refused + failed;

      const tokens = data.tokens || { jev: 0, llm: 0 };

      // Outcome summary stat tiles
      const tiles = el("div", [
        statTile("Recovered", String(recovered), "", "Patched & verified in session", "var(--ok)"),
        statTile("Refused safely", String(refused), "", "No value invented", refused ? "var(--ok)" : undefined),
        statTile("Failed / unfixable", String(failed), "", "Verification failed", failed ? "var(--bad)" : undefined),
        statTile("Session Tokens", String(tokens.llm), "llm", `Jev tokens: ${tokens.jev}`),
      ], { class: "cards", style: "margin-bottom: 16px;" });
      container.appendChild(tiles);

      // Outcome visual bar
      if (total > 0) {
        const barWrap = el("div", null, {
          style: "height: 8px; width: 100%; border-radius: 4px; overflow: hidden; display: flex; background: var(--soft); margin-bottom: 20px;",
        });
        if (recovered > 0) {
          barWrap.appendChild(el("div", null, {
            style: `height: 100%; width: ${(recovered / total) * 100}%; background: var(--ok);`,
            title: `Recovered: ${recovered}`,
          }));
        }
        if (refused > 0) {
          barWrap.appendChild(el("div", null, {
            style: `height: 100%; width: ${(refused / total) * 100}%; background: var(--warn);`,
            title: `Refused safely: ${refused}`,
          }));
        }
        if (failed > 0) {
          barWrap.appendChild(el("div", null, {
            style: `height: 100%; width: ${(failed / total) * 100}%; background: var(--bad);`,
            title: `Failed: ${failed}`,
          }));
        }
        container.appendChild(barWrap);
      }

      // Tier table
      const byTier = data.by_tier || {};
      const t0 = byTier["0"] || { n: 0, mttr_ms: { p50: 0, p95: 0 }, heal_ms: { p50: 0, p95: 0 } };
      const t1 = byTier["1"] || { n: 0, mttr_ms: { p50: 0, p95: 0 }, heal_ms: { p50: 0, p95: 0 } };

      const fmtTiming = (stats) => {
        if (!stats || !stats.p50) return "—";
        return `${Math.round(stats.p50)} ms / ${Math.round(stats.p95)} ms`;
      };

      const tableWrap = el("div", null, { style: "overflow-x: auto; margin-bottom: 20px;" });
      const table = el("table", null, { style: "width: 100%; border-collapse: collapse; font-size: var(--fs-sm);" });

      const thead = el("thead", [
        el("tr", [
          el("th", "Tier", { style: "text-align: left; padding: 6px 10px;" }),
          el("th", "Count (n)", { style: "text-align: left; padding: 6px 10px;" }),
          el("th", "MTTR (p50 / p95)", { style: "text-align: left; padding: 6px 10px;" }),
          el("th", "heal_ms (p50 / p95)", { style: "text-align: left; padding: 6px 10px;" }),
        ]),
      ]);
      table.appendChild(thead);

      const tbody = el("tbody", [
        el("tr", [
          el("td", "Tier 0 (cached fix)", { style: "padding: 6px 10px; font-weight: 500;" }),
          el("td", String(t0.n || 0), { class: "mono", style: "padding: 6px 10px;" }),
          el("td", t0.n ? fmtTiming(t0.mttr_ms) : "—", { class: "mono", style: "padding: 6px 10px;" }),
          el("td", t0.n ? fmtTiming(t0.heal_ms) : "—", { class: "mono", style: "padding: 6px 10px;" }),
        ], { style: "border-top: 1px solid var(--line);" }),
        el("tr", [
          el("td", "Tier 1 (diagnosed)", { style: "padding: 6px 10px; font-weight: 500;" }),
          el("td", String(t1.n || 0), { class: "mono", style: "padding: 6px 10px;" }),
          el("td", t1.n ? fmtTiming(t1.mttr_ms) : "—", { class: "mono", style: "padding: 6px 10px;" }),
          el("td", t1.n ? fmtTiming(t1.heal_ms) : "—", { class: "mono", style: "padding: 6px 10px;" }),
        ], { style: "border-top: 1px solid var(--line);" }),
      ]);
      table.appendChild(tbody);
      tableWrap.appendChild(table);
      container.appendChild(tableWrap);

      // Refusal list
      const refusals = (data.refusals || []).slice(-10).reverse();
      const refSection = el("div", [
        el("h4", "Safe refusals (no value invented)", { style: "margin: 0 0 8px 0; font-size: var(--fs-base);" }),
      ]);

      if (!refusals.length) {
        refSection.appendChild(el("p", "No refusals in this session.", { class: "muted" }));
      } else {
        const list = el("div", null, { style: "display: flex; flex-direction: column; gap: 6px;" });
        for (const r of refusals) {
          const item = el("div", [
            el("span", r.tool || "tool", { class: "mono", style: "font-weight: 500;" }),
            document.createTextNode(" · "),
            el("span", r.reason || "NO_SAFE_VALUE", { class: "pill warn plain", style: "font-size: var(--fs-xs);" }),
            document.createTextNode(" "),
            el("span", "refused safely: no value invented", { class: "muted", style: "font-size: var(--fs-xs);" }),
          ], {
            style: "padding: 6px 10px; background: var(--soft); border-radius: var(--r-sm); font-size: var(--fs-sm);",
          });
          list.appendChild(item);
        }
        refSection.appendChild(list);
      }
      container.appendChild(refSection);
    },
  });
})();
