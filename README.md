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
- **`src/make_session.py`** — writes a full canonical-schema session directory
  (`t0a/t0b/t0c/trial.parquet`) in one command — the on-disk contract
  `swimlab.pipeline.run_session` reads, and the template a real Movella DOT export
  will follow once `swimlab/io.py` exists.
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

### Varying a swimmer

Every generator knob is a CLI flag on `export_session.py --mock`:

| flag | varies | notes |
|------|--------|-------|
| `--mock` | technique archetype | the biggest lever |
| `--seed N` | a different *individual* of that archetype | re-rolls bump amplitudes, jitter, timing — unlimited distinct swimmers |
| `--baseline D` | habitual prone head pitch, ° | −5…12 realistic |
| `--mount X Y Z` | sensor mount offset, ° | calibration removes it; large offsets stress the recovery |
| `--n-lengths N` | session length | 4 = T7; <4 can trip `INSUFFICIENT_CYCLES` |
| `--stroke-period S` | swim tempo, s/stroke | smaller = faster = more strokes/breaths |
| `--breathe-every N` | breathing pattern | 3 = bilateral (alternating), 2 = unilateral (one side; `asymmetry_index` becomes undefined) |
| `--mount-slip D` | sensor slip during the swim, °/min | models the sensor working loose |
| `--clean` | turns sensor noise off | a clean round-trip |

```bash
# a fast bilateral rotator, long session
python src/export_session.py --mock ROTATOR --seed 3 --stroke-period 1.1 --n-lengths 6 --out r3.json

# a lifter whose sensor slips 5°/min, high habitual pitch
python src/export_session.py --mock LIFTER --seed 9 --mount-slip 5 --baseline 10 --out l9.json

# a batch of ten distinct lifters
for s in $(seq 1 10); do python src/export_session.py --mock LIFTER --seed $s --out lifter_$s.json; done
```

For total control (any parameter, custom logic) call the library directly —
`synth.generate_trial(...)` exposes the same knobs plus a few more
(`gyro_bias_walk`, `yaw_corruption_scale`).

## Generate a full session (parquet) for `run_session`

The viewer's `data.json` is pipeline *output*. To exercise the pipeline itself
against on-disk files — or to see the "sensor data" layer a real export becomes —
write a session directory:

```bash
python src/make_session.py --mock LIFTER --seed 42 --out sessions/s01
#   -> sessions/s01/{t0a,t0b,t0c,trial}.parquet  (+ ground_truth.json)
python -c "from swimlab.pipeline import run_session; \
           t,f = run_session('sessions/s01'); print(t.head()); print('flags:', f)"
```

`--clean` drops sensor noise (a zero-noise round-trip); `--n-lengths`, `--baseline`,
and `--mount` vary the swim and the sensor setup. The parquet files carry only the
canonical schema (`t / quat_* / acc_* / gyr_* / mag_*`) — exactly what `io.py` must
normalise a real Movella DOT download into.

## Status & scope

This is a visualization prototype, deliberately separate from `swimlab` (whose
charter is offline analysis only). It is **downstream of validating the core
hypothesis** — whether head pitch is a real diagnostic gate — which requires real
pool data. Treat everything here as a demonstration of what the interface could be,
not as a product or a validated coaching tool.
