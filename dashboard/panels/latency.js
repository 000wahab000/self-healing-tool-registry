// Call latency per tool and agent, from the live call log (AC-113)
(function () {
  function el(tag, text, attrs = {}) {
    const node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = String(text);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") node.className = v;
      else node.setAttribute(k, v);
    }
    return node;
  }
  const ms = (v) => Math.round(v) + " ms";

  window.HealerPanels.register({
    id: "latency",
    title: "Call latency",
    endpoint: "/api/metrics/latency",
    render(container, data) {
      container.replaceChildren();
      const head = el("div", null, { class: "head" });
      const h = el("div");
      h.append(el("p", "Live call log · since the last reset", { class: "eyebrow" }), el("h3", "Call latency per tool"));
      head.append(h);
      container.append(head);
      if (!data.total) {
        container.append(el("p", "No calls yet. Run a scenario on the Live tab.", { class: "muted" }));
        return;
      }
      const sum = el("p", null, { class: "muted" });
      sum.textContent = data.total + " calls · p50 " + ms(data.p50_ms) + " · p95 " + ms(data.p95_ms);
      const table = el("table", null, { class: "log" });
      const tr = el("tr");
      for (const c of ["Agent", "Tool", "Calls", "Errors", "p50", "p95"]) tr.append(el("th", c));
      const thead = el("thead"); thead.append(tr);
      const body = el("tbody");
      for (const r of data.rows) {
        const row = el("tr");
        row.append(el("td", r.agent), el("td", r.tool, { class: "mono" }), el("td", r.n), el("td", r.errors), el("td", ms(r.p50_ms)), el("td", ms(r.p95_ms)));
        body.append(row);
      }
      table.append(thead, body);
      const card = el("section", null, { class: "card scroll" });
      card.append(table);
      container.append(sum, card);
    },
  });
})();
