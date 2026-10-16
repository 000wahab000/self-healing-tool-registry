// Fix lifecycle panel (AC-80)
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

  function formatOp(o) {
    if (!o || typeof o !== "object") return String(o);
    const name = o.op || "op";
    if (name === "rename") return `rename ${o.from || ""} → ${o.to || ""}`;
    if (name === "cast") return `cast ${o.path || ""} → ${o.to || ""}`;
    if (name === "nest") return `nest ${o.path || ""} → ${o.to || ""}`;
    if (name === "add_header") return `add_header ${o.name || ""}`;
    if (name === "route") return `route → ${o.to || ""}`;
    if (name === "default") return `default ${o.path || ""}`;
    return `${name} ${JSON.stringify(o)}`;
  }

  window.HealerPanels.register({
    id: "lifecycle",
    title: "Fix Lifecycle & Reusable Rules",
    endpoint: "/api/metrics/lifecycle",
    render(container, data) {
      container.replaceChildren();

      const head = el("div", [
        el("div", [
          el("p", "Adaptive memory & rule promotion · store lifecycle", { class: "eyebrow" }),
          el("h3", "Fix Lifecycle & Reusable Rules"),
        ]),
      ], { class: "head", style: "margin-bottom: 12px;" });
      container.appendChild(head);

      if (!data) {
        container.appendChild(el("p", "No lifecycle data available offline.", { class: "muted" }));
        return;
      }

      // Snapshot telemetry unavailable notice
      const unavail = data.unavailable || [];
      if (unavail.includes("snapshots")) {
        container.appendChild(
          el("p", "Spec snapshots & precompute telemetry: not available yet in store contract.", {
            class: "muted",
            style: "font-size: var(--fs-xs); margin-bottom: 16px;",
          })
        );
      }

      const fixes = data.fixes || [];
      const rules = data.rules || [];

      if (!fixes.length && !rules.length) {
        container.appendChild(
          el("p", "No healed breaks or reusable rules recorded yet in this session.", { class: "muted" })
        );
        return;
      }

      // Render per-fingerprint fix lifecycle cards
      const fixesWrap = el("div", null, { style: "display: flex; flex-direction: column; gap: 12px; margin-bottom: 20px;" });
      for (const fix of fixes) {
        const isPromoted = fix.state === "active" || fix.state === "rule" || fix.wins > 0;
        const isRule = fix.state === "rule" || rules.includes(fix.fingerprint);

        const card = el("div", null, {
          style: "padding: 12px 14px; background: var(--soft); border-radius: var(--r); border: 1px solid var(--line); font-size: var(--fs-sm);",
        });

        // Top line: Tool + fingerprint
        const topRow = el("div", [
          el("span", fix.tool || "tool", { class: "mono", style: "font-weight: 600; font-size: var(--fs-base);" }),
          document.createTextNode(" "),
          el("span", fix.fingerprint, { class: "mono muted", style: "font-size: var(--fs-xs);" }),
        ], { style: "display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; margin-bottom: 8px;" });
        card.appendChild(topRow);

        // Lifecycle chips row: detected → candidate → verified/promoted → rule (N replays)
        const chipsRow = el("div", [
          el("span", "detected", { class: "pill good plain", style: "font-size: var(--fs-xs);" }),
          el("span", "→", { class: "muted" }),
          el("span", "candidate", { class: "pill good plain", style: "font-size: var(--fs-xs);" }),
          el("span", "→", { class: "muted" }),
          el(
            "span",
            isPromoted ? "verified/promoted" : "pending verification",
            {
              class: isPromoted ? "pill good plain" : "pill plain",
              style: "font-size: var(--fs-xs);",
            }
          ),
          el("span", "→", { class: "muted" }),
          el(
            "span",
            isRule ? `rule (${fix.tier0_replays || 0} replays)` : `rule (${fix.tier0_replays || 0} replays)`,
            {
              class: isRule || fix.tier0_replays > 0 ? "pill good plain" : "pill plain",
              style: "font-size: var(--fs-xs);",
            }
          ),
        ], { style: "display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 10px;" });
        card.appendChild(chipsRow);

        // Patch ops
        const ops = fix.ops || [];
        const opsRow = el("div", [
          el("span", "Patch ops: ", { class: "muted", style: "font-size: var(--fs-xs);" }),
        ]);
        if (!ops.length) {
          opsRow.appendChild(el("span", "—", { class: "muted" }));
        } else {
          for (const o of ops) {
            opsRow.appendChild(el("span", formatOp(o), { class: "op", style: "margin-right: 6px;" }));
          }
        }
        card.appendChild(opsRow);

        // Replay stats
        const firstTier = fix.first_heal_tier !== null && fix.first_heal_tier !== undefined ? fix.first_heal_tier : 1;
        const statsRow = el("div", [
          el("span", `First heal: Tier ${firstTier}`),
          document.createTextNode(" · "),
          el("span", `Tier-0 replays: ${fix.tier0_replays || 0}`),
          document.createTextNode(" · "),
          el("span", `Verified wins: ${fix.wins || 0}`),
        ], { class: "muted", style: "font-size: var(--fs-xs); margin-top: 8px;" });
        card.appendChild(statsRow);

        fixesWrap.appendChild(card);
      }
      container.appendChild(fixesWrap);

      // Promoted rules list
      if (rules.length) {
        const rulesBox = el("div", [
          el("h4", "Promoted reusable rules", { style: "margin: 0 0 8px 0; font-size: var(--fs-base);" }),
        ]);
        const rulesList = el("div", null, { class: "ops" });
        for (const r of rules) {
          rulesList.appendChild(el("span", r, { class: "op", style: "color: var(--ok);" }));
        }
        rulesBox.appendChild(rulesList);
        container.appendChild(rulesBox);
      }
    },
  });
})();
