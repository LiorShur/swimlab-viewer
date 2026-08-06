# swimlab app — architecture & product design

The blueprint for turning the validated `swimlab` analysis engine + the
multi-placement dashboards into a complete, native, freemium coaching app.
This is the contract we build against; it supersedes nothing in
`platform-design.md` (the analysis platform) — it wraps it into a product.

> **Framing that must survive into the product.** The core hypothesis (that
> these IMU metrics are a real diagnostic gate) is **not yet validated on real
> swimmers**. Everything user-facing — free or paid — stays a *coaching aid*,
> phrased as illustrative/hypothesis-based, never clinical. Selling "AI coaching"
> is fine; overclaiming is not.

---

## 1. The load-bearing decision: the engine stays Python, on a server

`swimlab` is ~200 tested cases of validated analysis (polars / scipy / orientation
maths). We do **not** rewrite it in JS/TS (throws away the guarantees, doubles
maintenance) and we do **not** run it in-app via Pyodide (fragile for
polars/scipy, and narration still needs a server for the API key). Instead:

```
 ┌─────────────┐   recording (CSV)    ┌──────────────┐   metrics + narration   ┌────────────┐
 │ swimlab-app │ ───────────────────▶ │ swimlab-api  │ ──────────────────────▶ │ swimlab-app│
 │ (Capacitor) │   per placement      │ (FastAPI)    │   JSON the UI renders    │  dashboards│
 └─────────────┘                      │  wraps swimlab│                          └────────────┘
        │ BLE / CSV import             │  + Anthropic  │
        ▼                              │  + Postgres   │
   Movella DOT                         └──────────────┘
```

| Component | What it is | Owns |
|---|---|---|
| **`swimlab`** | the Python engine, unchanged | calibrate → events → metrics → stats; `io` reader/writer; synth |
| **`swimlab-api`** (new) | thin FastAPI service wrapping the engine | processing, **server-side narration** (holds the Anthropic key), accounts, history, progress, **freemium entitlements** |
| **`swimlab-app`** (new) | React + **Capacitor** (iOS / Android / web) | capture (BLE / CSV import), placement + calibration UX, the per-placement dashboards, account/billing |

The current `swimlab-viewer` becomes the web build of `swimlab-app` (or its
staging ground); the Cloudflare narration worker becomes a legacy web-only path
(the app calls our own authenticated `/narrate`, **no worker URL prompt**).

---

## 2. Capture layer — the realities that shape the UX

The reference reader (`jiminghe/Xsens_DOT_PC_Reader`) is **PC live-streaming**.
Two hard physical facts change the product from "stream" to "record → offload":

1. **BLE does not work underwater** (2.4 GHz is absorbed by water). No live data
   mid-swim.
2. **120 Hz is recording-only**; BLE streaming caps at **60 Hz** (confirmed from
   the DOT enums).

So the real workflow is **onboard recording + offload**:

```
connect DOT → assign placement → calibration poses → START recording (flash, 120 Hz)
   → swim → STOP → OFFLOAD over BLE → upload to swimlab-api
```

This is *more* than the reference repo (it only streams). The recording-control +
file-offload BLE characteristics must be built and verified against the **real
device** — the one part that genuinely waits for hardware. We reimplement the DOT
BLE protocol in TypeScript (`@capacitor-community/bluetooth-le`) from the UUIDs +
the payload byte-layouts already extracted in `swimlab/io.py` (from `parser.py`).

**Before hardware** (point 1.3): the app imports our synthetic **Custom Mode 5**
CSVs (`io.write_dot_export`) behind the *same* "a recording arrived" interface the
BLE layer will later feed. Everything except the live BLE layer ships now; BLE is
stubbed behind a `CaptureSource` interface.

```
interface CaptureSource {
  listSensors(): Promise<SensorHandle[]>          // BLE scan  |  file picker
  record(placement, calibration): Promise<Recording>   // start/stop + offload  |  read a CSV
}
```

**Per-placement, multi-sensor** (points 1.2, 1.4): one swim = 1..N sensors, each
tagged with a placement (head, sacrum, wrist L/R, ankle L/R, upper arm L/R) and
its calibration poses. Maps straight onto the placement registry; the API runs
each placement's module and the cross-sensor **fusion** metrics when several are
present.

---

## 3. Data model (Postgres)

```
User(id, email, auth, tier, created_at)
Entitlement(user_id, feature, active, source, expires_at)      -- freemium, server-authoritative
Session(id, user_id, pool_length_m, protocol, recorded_at, notes)
Placement(id, session_id, placement_id, side, calibration_json, quality_flags)
Recording(id, placement_pk, storage_uri, payload_mode, sample_rate, checksum)  -- raw file (see privacy §8)
Metrics(id, placement_pk, metrics_json)          -- the per-placement metric payload
Fusion(id, session_id, fusion_json)              -- L/R symmetry, stroke-kick coord, etc.
Narrative(id, target_pk, lang, model, narrative_json, created_at)   -- cached AI narration
ProgressSnapshot(id, user_id, computed_at, stats_json)   -- cross-session trends (stats module)
```

`metrics_json` / `narrative_json` are exactly the payloads the dashboards already
consume, so the presentation layer is unchanged by where they come from.

---

## 4. API contract (first cut)

| Method | Endpoint | Tier | Purpose |
|---|---|---|---|
| `POST` | `/auth/*` | — | sign-up / login (JWT) |
| `POST` | `/sessions` | free | create a session (pool length, protocol) |
| `POST` | `/sessions/{id}/placements` | free | upload a recording for a placement → run pipeline → store + return metrics |
| `GET` | `/sessions` / `/sessions/{id}` | free | history (free tier: last N; paid: unlimited) |
| `POST` | `/sessions/{id}/narrate` | **paid** | server-side Anthropic narration for a placement/fusion, EN+HE, cached |
| `GET` | `/progress` | **paid** | cross-session improvement analysis (stats module) |
| `GET` | `/me/entitlements` | — | what the account may do |
| `POST` | `/billing/webhook` | — | RevenueCat / Stripe → flip entitlements |

Processing endpoints accept a **Custom Mode 5** CSV (or parquet) per placement,
validate with `io.validate_dot_export`, run calibrate→events→metrics, and — when
the session has several placements — the fusion metrics. Rule-based **findings**
are computed for everyone (free); **AI narration** is the paid upgrade on top.

---

## 5. Presentation parity (points 1.5, 1.6)

The head `dashboard.html` is the reference structure; the holistic app already
replicates it per placement (summary card → expandable full analysis → charts →
schematic → drills → findings, EN/HE + RTL). Porting to React components is
mechanical. Two deliberate additions to reach full parity with "animation options
(play speed etc.)":

- **Playback controls** on every schematic: play/pause, **speed** (0.5×–4×), and a
  **scrub** bar — replacing today's auto-loop.
- **Exact per-placement page structure** mirrored from the head dashboard (same
  sections, same order, same summary-first + expandable pattern).

Components (shared across placements, parameterised by placement):
`SummaryCard`, `MetricKPIs`, `TraceChart`, `MotionSchematic` (with controls),
`DrillsList` + `VideoModal`, `FindingsPanel`, `NarrationPanel`, `LanguageToggle`.

---

## 6. AI narration without a worker URL (point 1.7)

Narration moves **into `swimlab-api`** (it already mirrors `narrate.py`, now
placement-aware). The app calls `POST /sessions/{id}/narrate` authenticated by the
user's session; the **Anthropic key lives server-side**; results are cached
(`Narrative`), both languages in one call. No worker URL, no key in the client.
Cost control: paid-tier gating, caching, cheaper models (Haiku/Sonnet knobs
already exist), per-tier rate limits.

---

## 7. Freemium (point 3)

Enforced **server-side** on `Entitlement` (never client-side — trivially
bypassable). Billing via **RevenueCat** (wraps App Store / Play billing for
Capacitor) + Stripe for web; a webhook flips entitlements.

| Capability | Free | Paid |
|---|---|---|
| Single-sensor capture + core metrics | ✓ | ✓ |
| Rule-based findings (deterministic, no API cost) | ✓ | ✓ |
| Session history | last N | unlimited |
| **AI narration** (per placement + fusion) | — | ✓ |
| **Multi-sensor fusion** (L/R symmetry, coordination) | — | ✓ |
| **Progress / improvement analysis** | — | ✓ |

The free tier is genuinely useful (it's what we've already built) and costs us
nothing per-use; the paid tier is the LLM- and compute-heavy value.

---

## 8. Security, privacy, honesty

- **Anthropic key** server-side only.
- **Raw recordings** are personal data. Store encrypted; explicit retention +
  delete; never log raw content (mirror `swimlab` constraint 2 into the product).
- **Entitlements server-authoritative**; the client only *reflects* them.
- **Keep the hedging** in every narration and progress claim — coaching aid, not
  clinical fact, until the study validates the gate.

---

## 9. Honest risks

- **BLE record/offload is the biggest lift and the least de-riskable without the
  device.** Everything else builds now; this one layer waits for hardware.
- **Underwater = no live data** — the UX must be record→offload, not stream.
- **Real ops**: hosting, DB, auth, billing, store review. A product, not a
  weekend.
- **Unvalidated science** — see the framing note at the top.

---

## 10. Phased roadmap (value early, hardware-independent)

| Phase | Deliverable | Needs hardware? |
|---|---|---|
| **A** | `swimlab-api`: process a Custom-Mode-5 upload per placement → metrics; **server-side narration**; point the current web UI at it (drops the worker URL). Proves the whole loop today. | no |
| **B** | React + Capacitor shell: port the per-placement dashboards (with playback controls) into components; CSV import for placements; runs web + iOS/Android on synthetic data. | no |
| **C** | Accounts + history + **progress/improvement analysis** + freemium (auth, DB, entitlements, billing). | no |
| **D** | Real **BLE**: DOT connect + onboard record + offload + per-placement calibration; validate `io` on the first real file (already wired). | **yes** |

**Recommended start:** Phase A — the backend loop on synthetic data. It makes the
entire product real today, removes the worker-URL wart, and everything after it
(app shell, accounts, freemium) plugs into a working API.

---

## 11. Open decisions to lock before/while building

- Hosting + DB provider (managed Postgres + a container host).
- Auth: roll-our-own JWT vs a provider (Auth0/Clerk/Supabase).
- Billing: RevenueCat (native-first) confirmed? Stripe for web only?
- Free-tier history depth (N sessions) and any free monthly narration allowance.
- Coach vs swimmer roles (shared sessions, coach dashboards) — v1 or later?
