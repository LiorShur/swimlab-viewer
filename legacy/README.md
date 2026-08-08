# legacy — the original hosted web app (reference only)

This folder holds the **first** hosted web app (the `app_template.html`-based
holistic dashboard + `dashboard.html` / `sacrum.html`) and the Cloudflare
narration `worker/`. It is kept **for reference only** and is **no longer
deployed** — Firebase Hosting now serves the React/Capacitor app in `../native`
(built to `native/dist`), so the hosted site and the native app are the same.

Nothing here is wired into the live app. The shared backend (`../functions`)
and the engine are unchanged. If you ever need something from here (a bit of
copy, a drill list, a schematic), lift it into `../native`.

Contents:
- `index.html`, `dashboard.html`, `sacrum.html` — the built pages.
- `src/` — templates + `build.py`, `export_session.py`, `findings.py`,
  `narrate.py` (the backend keeps its own vendored copies under
  `../functions/swimbackend`).
- `worker/` — the standalone Cloudflare narration proxy (superseded by the
  `narrate` Cloud Function).
- `firebase-config.example.js` — the old runtime web-config shim (the native app
  uses build-time `VITE_FIREBASE_*` env instead).
