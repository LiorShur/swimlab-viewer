# swimlab-viewer

A self-contained web dashboard for a **swimlab** head-IMU swim session — pitch/roll
traces, per-breath metrics, an auto-generated summary, correction points, drills,
and a head-position schematic. Built to consume the `swimlab` analysis library;
`swimlab` itself stays a pure offline-analysis package (no app/UI code).

> **Prototype on synthetic data.** The current build renders a swimmer produced by
> swimlab's synthetic generator, not a real swim. The "technique target" shown in
> the head-position figure is the study's **hypothesis under test** (rotate to
> breathe, minimal lift), *not* a validated optimum — the pool study has not run.
> Correction points and drills are standard freestyle-breathing coaching cues,
> included illustratively. Nothing here is a clinical or validated finding yet.

## How it works

```
sensor / mock ──▶ swimlab pipeline ──▶ export_session.py ──▶ data.json ──▶ build.py ──▶ dashboard.html
              (calibrate→events→metrics)                    (payload)                (self-contained page)
```

- **`src/export_session.py`** — runs a session end-to-end through swimlab and writes
  the viewer payload. `--mock LIFTER` synthesises one swimmer (no hardware); `--set`
  builds the prefab multi-swimmer bundle for the dropdown; `--session DIR` will read
  a real Movella DOT export once `swimlab/io.py` is unblocked.
- **`src/build.py`** — inlines the payload into `src/template.html` to produce the
  single-file `dashboard.html`.
- **`dashboard.html`** — the built page. Open it directly in any browser; no server,
  no external requests.

## In the page

- **Swimmer dropdown** — switch between the prefab archetypes (each a real pipeline
  run), re-rendering the whole dashboard live.
- **Import session…** — load a `data.json` you generated offline with
  `export_session.py` (any archetype/seed). The generation is Python; the import and
  render happen in-browser. This is how you view a "random" swimmer: make the file,
  then import it. (Because the analysis pipeline is Python/numpy/scipy, it cannot run
  inside the static page — the export step does the heavy lifting.)

## Regenerate

```bash
pip install -e path/to/swimlab            # the analysis library

# the prefab dropdown bundle (what the committed dashboard ships):
python src/export_session.py --set --out sessions.json
python src/build.py --data sessions.json --out dashboard.html

# or a single swimmer you can Import in the page:
python src/export_session.py --mock ROTATOR --seed 7 --out data.json
```

Archetypes: `LIFTER`, `ROTATOR` (clean technique), `MIXED` (inconsistent),
`ASYMMETRIC` (left/right imbalance), `FLAT` (barely rolls).

## Status & scope

This is a visualization prototype, deliberately separate from `swimlab` (whose
charter is offline analysis only). It is **downstream of validating the core
hypothesis** — whether head pitch is a real diagnostic gate — which requires real
pool data. Treat everything here as a demonstration of what the interface could be,
not as a product or a validated coaching tool.
