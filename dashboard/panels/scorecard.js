// Benchmark scorecard panel (AC-78)
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

  function median(nums) {
    if (!nums || !nums.length) return 0;
    const sorted = [...nums].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  }

  window.HealerPanels.register({
    id: "scorecard",
    title: "Benchmark Scorecard",
    endpoint: "/api/metrics/scorecard",
    render(container, data) {
      container.replaceChildren();

      const head = el("div", [
        el("div", [
          el("p", "Measured benchmark results · REPORT.md", { class: "eyebrow" }),
          el("h3", "Benchmark Scorecard"),
        ]),
      ], { class: "head", style: "margin-bottom: 16px;" });
      container.appendChild(head);

      if (!data || !data.available) {
        const hint = (data && data.hint) || "python -m bench.run --agent scripted --n 3";
        container.appendChild(
          el("p", [
            document.createTextNode("No benchmark scorecard data available. Run "),
            el("code", hint),
            document.createTextNode(" to generate a report."),
          ], { class: "muted" })
        );
        return;
      }

      const z = data.ztar || { healing: { adapted: 0, runs: 0 }, baseline: { adapted: 0, runs: 0 } };
      const fp = data.false_patch || { false_patches: 0, healed: 0 };
      const sr = data.safe_refusal || { refused: 0, runs: 0 };
      const tokensList = data.tokens || [];

      const ztarH = z.healing.runs ? Math.round((z.healing.adapted / z.healing.runs) * 100) : 0;
      const ztarB = z.baseline.runs ? Math.round((z.baseline.adapted / z.baseline.runs) * 100) : 0;
      const srRate = sr.runs ? Math.round((sr.refused / sr.runs) * 100) : 0;

      const overMed = median(tokensList.map((t) => t.healing_overhead || 0));

      const tiles = el("div", [
        statTile(
          "ZTAR (Healing vs Baseline)",
          `${ztarH}% vs ${ztarB}%`,
          "",
          `${z.healing.adapted}/${z.healing.runs} adapted vs ${z.baseline.adapted}/${z.baseline.runs}`,
          "var(--ok)"
        ),
        statTile(
          "False-Patch Rate",
          `${fp.false_patches} / ${fp.healed} healed`,
          "",
          "Target: 0 wrong final states",
          fp.false_patches === 0 ? "var(--ok)" : "var(--bad)"
        ),
        statTile(
          "Safe-Refusal Rate",
          `${srRate}%`,
          `(${sr.refused}/${sr.runs})`,
          "M8 & M6-N: 0 invented values",
          srRate === 100 ? "var(--ok)" : undefined
        ),
        statTile(
          "Token Overhead (median)",
          String(overMed),
          "tokens",
          "Mutated run vs CLEAN median"
        ),
      ], { class: "cards", style: "margin-bottom: 20px;" });
      container.appendChild(tiles);

      // Per-scenario compact table
      const scenarios = data.per_scenario || [];
      if (scenarios.length) {
        const tableWrap = el("div", null, { style: "overflow-x: auto; margin-top: 16px;" });
        const table = el("table", null, { style: "width: 100%; border-collapse: collapse; font-size: var(--fs-sm);" });

        const thead = el("thead", [
          el("tr", [
            el("th", "Scenario", { style: "text-align: left; padding: 6px 10px;" }),
            el("th", "Self-healing", { style: "text-align: left; padding: 6px 10px;" }),
            el("th", "Baseline", { style: "text-align: left; padding: 6px 10px;" }),
            el("th", "Outcome details", { style: "text-align: left; padding: 6px 10px;" }),
          ]),
        ]);
        table.appendChild(thead);

        const tbody = el("tbody");
        for (const item of scenarios) {
          const isHealingPass = item.healing && !item.healing.startsWith("0/");
          const isBaselinePass = item.baseline && !item.baseline.startsWith("0/");

          const healCell = el("td", [
            el("span", isHealingPass ? "✓ " : "✗ ", { style: `color: ${isHealingPass ? "var(--ok)" : "var(--bad)"}` }),
            document.createTextNode(item.healing || "—"),
          ], { style: "padding: 6px 10px;" });

          const baseCell = el("td", [
            el("span", isBaselinePass ? "✓ " : "✗ ", { style: `color: ${isBaselinePass ? "var(--ok)" : "var(--bad)"}` }),
            document.createTextNode(item.baseline || "—"),
          ], { style: "padding: 6px 10px;" });

          let detailText = "—";
          if (item.baseline_failure && item.refusal_reason) {
            detailText = `${item.baseline_failure} · ${item.refusal_reason}`;
          } else if (item.baseline_failure) {
            detailText = item.baseline_failure;
          } else if (item.refusal_reason) {
            detailText = item.refusal_reason;
          }

          const tr = el("tr", [
            el("td", item.scenario, { class: "mono", style: "padding: 6px 10px; font-weight: 500;" }),
            healCell,
            baseCell,
            el("td", detailText, { class: "muted", style: "padding: 6px 10px;" }),
          ], { style: "border-top: 1px solid var(--line);" });
          tbody.appendChild(tr);
        }
        table.appendChild(tbody);
        tableWrap.appendChild(table);
        container.appendChild(tableWrap);
      }

      // Footer
      const footer = el("div", [
        el("span", [document.createTextNode("Source: "), el("code", data.source || "REPORT.md")]),
        el("span", `Generated: ${data.generated_at || "—"}`),
        el("span", "Measured by bench/run.py", { style: "color: var(--ok);" }),
      ], {
        class: "muted",
        style: "margin-top: 16px; font-size: var(--fs-xs); display: flex; gap: 16px; flex-wrap: wrap; border-top: 1px solid var(--line); padding-top: 12px;",
      });
      container.appendChild(footer);
    },
  });
})();
