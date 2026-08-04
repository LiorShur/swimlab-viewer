# swimlab platform — multi-sensor design

Blueprint for growing the head-IMU demo into a comprehensive, multi-sensor swim
analysis platform. **Synthetic-first**: every module is built and tested against
a generated swimmer with known ground truth, then validated on real Movella/Xsens
DOT recordings once they exist (exactly how the head module was built).

Status: design. Nothing here is committed to real data yet.

---

## 1. Layers

```
 capture ─▶ sync ─▶ placement calibration ─▶ per-placement modules ─▶ fusion ─▶ interpretation / viewer
 (onboard    (align   (sensor→segment          (segment metrics +      (one     (KPIs, plain card,
  logging)    clocks)  transform per placement)  quality flags)         timeline) drills, narration)
```

The current app is the right-hand end (head module + viewer). This doc defines
the left-hand plumbing that makes it a platform.

---

## 2. The core abstraction: **placement**, not sensor

The same physical DOT can be worn on the head, sacrum, either wrist, either
upper arm, either ankle. Interpretation depends entirely on **where it was** and
**how it was calibrated** — so the platform is organised around *placements*, not
sensors. Each recording declares its placement; the pipeline routes to that
placement's calibration + module.

### Placement registry (one entry per body location)

```
Placement:
  id            "sacrum" | "wrist_l" | "wrist_r" | "upper_arm_l" | ... | "head"
  segment       body segment it measures (pelvis, forearm, ...)
  calibration   the pose protocol + sensor→segment transform for this location
  module        the analysis module (events + metrics) for this segment
  metrics       the metric keys this placement can produce
  frame         anatomical sign conventions (like the head's pitch/roll/yaw notes)
```

"Same sensor, placed differently" = pick a different registry entry for that
recording. Nothing else changes upstream — the canonical dataframe schema is
already placement-agnostic (see §4).

---

## 3. The unified synthetic swimmer (build FIRST)

The key to consistent multi-sensor work: **one kinematic swimmer body model**
from which *every* placement's virtual sensor is derived. Do NOT generate each
sensor independently — that makes cross-sensor fusion untestable.

```
synth.generate_swim(archetype, ...) ─▶ body kinematics over time
      │   (pelvis pose, per-limb segment poses, stroke cycle, kick cycle,
      │    push-offs, turns, per-length structure, tempo, fatigue drift)
      ▼
synth.virtual_sensor(body, placement, mount_offset, noise) ─▶ canonical dataframe
      (samples the segment's orientation + acceleration at the placement,
       adds mount offset + DOT-like noise/bias → the same schema io.py returns)
```

Ground truth (true stroke count, tempo, lengths, roll amplitude, L/R symmetry,
kick rate, push-off times) comes from the body model and is carried alongside
each generated trace, so every metric has a known target to test against — the
same contract the head module already uses.

---

## 4. Canonical schema — unchanged

Every reader and every virtual sensor returns the existing canonical dataframe
(`t, quat_*, acc_*, gyr_*, mag_*`). Placement changes calibration + metrics, not
the schema. Magnetometer stays logged-but-unused (pool-hall disturbance) for all
placements.

---

## 5. Per-placement module contract

Each module mirrors the head module's shape:

```
calibrate(pose_a, pose_b)         → sensor→segment transform + pose sanity flag
apply(trial, transform)           → calibrated segment angles/accel
detect_events(calibrated)         → strokes / kicks / push-offs / turns (+ reasons)
metrics(calibrated, events)       → metric table (pure: df in, df out)
```

Rules carried over from the head module: metrics are **pure** functions; every
metric has a synth unit test against known truth; rejected cycles are returned
with a reason code (never silently dropped); quality flags accumulate in a
`flags` column; thresholds live in `config.yaml`, not in code.

---

## 6. Calibration protocols (per placement)

Like the head's T0a (upright) + T0b (prone float) pair, each placement needs a
short, repeatable pose protocol to build the sensor→segment transform, plus a
pose-sanity check that flags a badly-performed pose instead of proceeding.

| Placement | Calibration poses (draft — validate on real swimmers) |
|---|---|
| Head | T0a upright gaze-horizontal, T0b prone float *(shipped)* |
| Sacrum | Upright stand + prone glide (streamline) |
| Wrist L/R | Arm extended overhead in streamline + arm at side |
| Upper arm L/R | Arm at side + arm forward-horizontal |
| Ankle L/R | Standing + prone glide (feet neutral) |

Because placement varies each session (point 2 of the brief), calibration is
**per-recording**, and the transform is stored with that recording.

---

## 7. Fusion & data model

A session is multiple placement streams (+ optional HR) on **one timeline**.

```
Session:
  pool_length_m         25 | 50            (the only source of absolute distance)
  placements[]          { placement_id, calibration, canonical_df, metrics }
  hr_stream?            { t, bpm }         (separate modality — see §9)
  events                merged lengths / strokes / kicks / push-offs / turns
  session_metrics       whole-swim + per-length + fusion metrics
```

Fusion metrics are the payoff of multiple sensors: L/R symmetry (wrist_l vs
wrist_r), stroke–kick coordination (wrist vs ankle), roll vs breath (sacrum vs
head), and HR vs tempo/effort.

**Time sync** is the hard prerequisite: R/L pairs and HR must share a clock.
Movella's SDK supports multi-sensor sync; onboard-recorded sessions need a sync
step (a shared start marker / SDK heading-reset). This is Phase-2 plumbing, not a
per-module concern.

---

## 8. Metrics catalogue (targets)

| Placement | Headline metrics |
|---|---|
| Head *(shipped)* | breath Δpitch, peak roll, roll:pitch, asymmetry, pitch drift |
| **Sacrum** | **lengths, stroke count, stroke rate/tempo, distance (×pool len), body-roll amplitude, L/R roll symmetry, push-off count/interval, pace drift** |
| Wrist L/R | stroke phases (catch/pull/recovery), stroke count, entry/exit timing, per-arm symmetry |
| Upper arm L/R | shoulder rotation, elbow-high catch proxy |
| Ankle L/R | kick count, kick rate, amplitude, L/R kick symmetry |
| HR (fusion) | HR vs tempo, drift across a set, recovery between reps |

Sacrum is the highest-value single sensor — it alone delivers the time / lengths
/ stroke-count / stroke-rate / distance set from the brief's point 4.

---

## 9. Honest constraints (design around these)

- **No absolute distance from an IMU.** Distance = lengths × pool length; per-
  stroke distance = pool length ÷ strokes-per-length. Double-integrating
  acceleration drifts and is not used.
- **Bluetooth doesn't work underwater** → onboard **recording**, offload after
  the swim. No real-time in the water.
- **Heart rate is a different modality** — the DOT can't measure it. Use a strap
  that logs internally (e.g. Polar H10) to dodge the underwater-BT problem; merge
  on the timeline in fusion.
- **Magnetometer / yaw unusable** in pool halls — gravity-referenced pitch/roll
  only, for every placement (already the head module's rule).
- **Multi-sensor sync** is the real engineering cost of R/L pairs + HR.

---

## 10. Repo split

Keep the tested analysis core clean; let the product layer move fast.

- **`swimlab`** (analysis engine, library): synth body model + virtual sensors,
  placement registry, per-placement calibration + modules, fusion, stats. Its
  charter ("offline analysis only") stays intact — it stays a library.
- **`swimlab-viewer`** (the app): capture/offload UX, placement declaration +
  calibration flow, per-placement + fusion viewer modules, narration, history.

---

## 11. Phased roadmap

| Phase | Deliverable | Status |
|---|---|---|
| 0 | Placement registry + unified synth body model + `virtual_sensor()` (head re-expressed through it, no metric change) | **done** — head reproduced byte-for-byte (`tests/test_platform.py`) |
| 1 | **Sacrum module** end-to-end on synth → lengths, stroke count/rate, tempo, distance, roll symmetry, push-offs; a sacrum viewer module | **done** — `swimlab.sacrum` + `sacrum.html` |
| 2 | Wrist L/R + the **fusion + time-sync layer** (proves R/L symmetry) | **wrist done** (`swimlab.wrist` + `symmetry()`); shared-clock time-sync still to do for onboard-recorded sessions |
| 3 | Ankle L/R (kick metrics) | planned |
| 4 | HR ingest + fusion metrics | planned |
| 5 | App polish: multi-placement session UX, calibration wizard, history | planned |
| ✓ | Validate the whole stack on real DOT recordings when hardware lands | pending hardware |

**Done so far:** Phases 0 and 1, plus the wrist L/R module with the first
two-sensor fusion metric (L/R symmetry + antiphase check). All built and
unit-tested against `synth.generate_swim()` ground truth in the `swimlab` engine.

**Next up:** the time-sync layer (a shared start marker for onboard-recorded R/L
pairs) to complete Phase 2, then ankle kick metrics (Phase 3).
