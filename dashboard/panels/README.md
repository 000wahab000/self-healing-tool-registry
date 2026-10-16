# Dashboard Panels

Modular panels for the metrics view. Each panel is a self-contained JavaScript file registering with `window.HealerPanels`.

## How to add a panel

1. Create `dashboard/panels/<name>.js`.
2. Register the panel:
   ```javascript
   window.HealerPanels.register({
     id: "<name>",
     title: "Panel Title",
     endpoint: "/api/metrics/<name>", // or null if no dedicated endpoint
     render(el, data, state) {
       // el: <section class="card pad" data-panel="<name>">
       // data: response from endpoint (or null if offline/no endpoint)
       // state: latest dashboard state from poll()
     }
   });
   ```
3. Add `<script src="/panels/<name>.js" defer></script>` to `dashboard/index.html` after `registry.js`.
4. If using an endpoint, add a route to `dashboard/app.py` and an offline stub to `Demo.handle()` in `dashboard/index.html`.
