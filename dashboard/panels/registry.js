// Dashboard panel slot registry (AC-77)
// Each panel: { id, title, endpoint|null, render(el, data, state) }
(function () {
  const panels = [];
  const lastFetched = new Map();
  const cachedData = new Map();
  const inFlight = new Set();
  let mountedContainer = null;

  function mountPanel(panel, container) {
    if (!container) return null;
    let section = container.querySelector(`[data-panel="${panel.id}"]`);
    if (!section) {
      section = document.createElement("section");
      section.className = "card pad";
      section.dataset.panel = panel.id;
      container.appendChild(section);
    }
    return section;
  }

  window.HealerPanels = {
    get panels() {
      return [...panels];
    },

    register(panel) {
      if (!panel || !panel.id) return;
      if (panels.some((p) => p.id === panel.id)) return;
      panels.push(panel);
      if (mountedContainer) {
        mountPanel(panel, mountedContainer);
      }
    },

    mountAll(container) {
      if (typeof container === "string") {
        container = document.querySelector(container) || document.getElementById(container);
      }
      if (!container) return;
      mountedContainer = container;
      for (const panel of panels) {
        mountPanel(panel, container);
      }
    },

    async refresh(state) {
      if (!mountedContainer) {
        const c =
          document.getElementById("panels-container") ||
          document.getElementById("panels") ||
          document.querySelector("[data-panels]");
        if (c) this.mountAll(c);
      }
      if (!mountedContainer) return;

      const now = Date.now();
      for (const panel of panels) {
        const el = mountPanel(panel, mountedContainer);
        if (!el) continue;

        try {
          let data = cachedData.get(panel.id) ?? null;
          if (panel.endpoint) {
            const last = lastFetched.get(panel.id) || 0;
            if (now - last >= 5000 && !inFlight.has(panel.id)) {
              inFlight.add(panel.id);
              try {
                if (window.Demo && window.Demo.on && typeof window.Demo.handle === "function") {
                  data = await window.Demo.handle(panel.endpoint).catch(() => null);
                } else if (typeof window.call === "function") {
                  data = await window.call(panel.endpoint).catch((err) => {
                    if (window.Demo && window.Demo.on) return null;
                    if (err && err.message && err.message.includes("unknown")) return null;
                    throw err;
                  });
                } else {
                  const res = await fetch(panel.endpoint);
                  data = res.ok ? await res.json() : null;
                }
              } catch (err) {
                if ((window.Demo && window.Demo.on) || (err && err.message && err.message.includes("unknown"))) {
                  data = null;
                } else {
                  throw err;
                }
              } finally {
                inFlight.delete(panel.id);
                lastFetched.set(panel.id, now);
                cachedData.set(panel.id, data);
              }
            }
          }

          if (typeof panel.render === "function") {
            await panel.render(el, data, state);
          }
        } catch (err) {
          el.replaceChildren();
          const p = document.createElement("p");
          p.className = "muted";
          p.style.color = "var(--bad, #f87171)";
          p.textContent = `Panel error (${panel.id}): ${err && err.message ? err.message : String(err)}`;
          el.appendChild(p);
        }
      }
    },

    reset() {
      panels.length = 0;
      lastFetched.clear();
      cachedData.clear();
      inFlight.clear();
      mountedContainer = null;
    },
  };
})();
