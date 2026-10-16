/* Shared UI: theme toggle (system -> light -> dark). The stored choice is applied before first paint by the inline <head> snippet on each page. */
(function () {
  var KEY = "theme", ORDER = ["system", "light", "dark"], LABEL = { system: "Theme: Auto", light: "Theme: Light", dark: "Theme: Dark" };
  function read() { try { var v = localStorage.getItem(KEY); return ORDER.indexOf(v) < 0 ? "system" : v; } catch (e) { return "system"; } }
  function write(v) { try { localStorage.setItem(KEY, v); } catch (e) { /* storage blocked: the choice lasts for this page only */ } }
  function toggles() { return Array.prototype.slice.call(document.querySelectorAll("[data-theme-toggle]")); }
  function apply(v) {
    if (v === "system") delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = v;
    toggles().forEach(function (b) { b.textContent = LABEL[v]; b.setAttribute("aria-label", LABEL[v] + ". Click to change."); b.dataset.mode = v; });
  }
  function init() {
    apply(read());
    toggles().forEach(function (b) {
      b.addEventListener("click", function () {
        var next = ORDER[(ORDER.indexOf(read()) + 1) % ORDER.length];
        write(next); apply(next);
      });
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
