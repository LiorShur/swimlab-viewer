"""Export a swimlab session into the JSON the viewer dashboard consumes.

This is the interface layer between the analysis pipeline and the app: it runs a
session end-to-end through swimlab (calibrate -> events -> metrics) and writes a
compact ``data.json`` for ``build.py`` to inline into the dashboard.

Two input modes:

* ``--session DIR`` -- read a real session directory of canonical-schema parquet
  files (``t0a.parquet``, ``t0b.parquet``, ``trial.parquet``) via
  ``swimlab.pipeline.run_session``. This is the path a real Movella DOT export
  will take once ``swimlab/io.py`` is unblocked.
* ``--mock ARCHETYPE`` -- synthesise a swimmer with swimlab's generator (the
  "mock sensor data file" path). No hardware required.

The viewer depends on swimlab as a library; keep swimlab itself free of any app
or UI code (its charter is offline analysis only).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

# ``roll:pitch`` target values are illustrative references for the demo head
# schematic; the "optimal" technique is the study's hypothesis, not validated.
_REFERENCE_APEX = {"apex_pitch": 4.0, "apex_roll": 68.0}

# Prefab swimmers for the viewer dropdown: a spread of archetypes, each with its
# own habitual head pitch and sensor mount, run through the real pipeline.
# (label, archetype, seed, pitch_baseline_deg, mount_offset_deg, swimmer_id)
_PREFAB = [
    ("Lifter · S-01", "LIFTER", 100, 5.0, (4.0, -3.0, 11.0), "S-01"),
    ("Rotator · S-02", "ROTATOR", 100, 3.0, (-6.0, 5.0, 14.0), "S-02"),
    ("Mixed · S-03", "MIXED", 100, 6.0, (8.0, -4.0, 9.0), "S-03"),
    ("Asymmetric · S-04", "ASYMMETRIC", 100, 4.0, (2.0, 7.0, 13.0), "S-04"),
    ("Flat · S-05", "FLAT", 100, 2.0, (-3.0, -6.0, 16.0), "S-05"),
]
_GATE_THRESHOLD_DEG = 13.5  # lifter/rotator separation from the integration gate


def _attach_findings(payload: dict) -> dict:
    """Attach the rule-based, placement-aware findings block (headline + summary
    + grounded coaching). Deterministic; no API call. See ``findings.py``."""
    import findings
    payload["findings"] = findings.findings_for(payload)
    return payload


def _trim(x, d: int = 2):
    """Round a number; pass ``None`` through unchanged.

    Some summary metrics are legitimately undefined -- e.g. ``asymmetry_index``
    when a swimmer breathes unilaterally (all breaths on one side), or
    ``mean_roll_pitch_ratio`` for a swimmer whose roll never clears the
    threshold. The viewer renders ``null`` as an em dash, so we carry it through
    rather than crash.
    """
    return None if x is None else round(float(x), d)


def _package(cal, gt, pb, summ, pushoffs, flags) -> dict:
    """Assemble the viewer payload from pipeline outputs."""
    t = cal["t"].to_numpy()
    pitch = cal["pitch_deg"].to_numpy()
    roll = cal["roll_deg"].to_numpy()
    step = max(1, len(t) // 1500)  # keep the payload light (multi-swimmer bundle)

    breaths = []
    for r in pb.iter_rows(named=True):
        breaths.append(
            {
                k: (_trim(v) if isinstance(v, float) else v)
                for k, v in r.items()
                if k in (
                    "t_start", "t_end", "side", "d_pitch_breath",
                    "peak_roll_breath", "roll_pitch_ratio", "breath_duration",
                    "excluded", "exclusion_reason",
                )
            }
        )

    _md = summ["mean_d_pitch_breath"][0]
    mean_dpitch = 0.0 if _md is None else float(_md)  # 0 valid breaths -> treat as 0
    return {
        "swimmer_id": gt.get("swimmer_id", "S-01 (synthetic)"),
        "session": "T7 — 4×25 m front crawl, breathing every 3",
        "mount_offset_deg": [_trim(v, 1) for v in gt.get("mount_offset_deg", [0, 0, 0])],
        # The archetype the swimmer was *generated* from (ground truth). The
        # pipeline never sees this -- it only measures d_pitch and classifies
        # into the binary Lifter/Rotator gate below, which can differ (e.g. FLAT
        # "lifts by default" and reads as Lifter).
        "archetype": gt.get("archetype", ""),
        "detected_pattern": "Lifter" if mean_dpitch > _GATE_THRESHOLD_DEG else "Rotator",
        "gate_threshold_deg": _GATE_THRESHOLD_DEG,
        "summary": {
            "mean_d_pitch_breath": _trim(mean_dpitch),
            "pitch_variability": _trim(summ["pitch_variability"][0]),
            "asymmetry_index": _trim(summ["asymmetry_index"][0], 3),
            "mean_peak_roll_breath": _trim(summ["mean_peak_roll_breath"][0], 1),
            "mean_roll_pitch_ratio": _trim(summ["mean_roll_pitch_ratio"][0], 3),
            "n_breaths": int(summ["n_breaths"][0]),
            "n_valid": int(summ["n_valid"][0]),
            "n_excluded": int(summ["n_excluded"][0]),
        },
        "flags": sorted(flags),
        "breaths": breaths,
        "traces": {
            "t": [_trim(x, 3) for x in t[::step]],
            "pitch": [_trim(x) for x in pitch[::step]],
            "roll": [_trim(x) for x in roll[::step]],
        },
        "pushoffs": [_trim(x) for x in pushoffs["t_peak"].to_numpy()]
        if "t_peak" in pushoffs.columns else [],
        "reference": _REFERENCE_APEX,
        "observed_apex": {
            "apex_pitch": _trim(mean_dpitch, 1),
            "apex_roll": _trim(summ["mean_peak_roll_breath"][0], 1),
        },
    }


def from_mock(archetype: str, seed: int, baseline: float,
              mount: tuple[float, float, float], swimmer_id: str = "S-01", *,
              n_lengths: int = 4, stroke_period_s: float = 1.4,
              breathe_every_n_strokes: int = 3, mount_slip_deg_per_min: float = 0.0,
              noise: bool = True) -> dict:
    """Synthesise a swimmer and run it through the pipeline (no hardware).

    The keyword knobs pass straight through to ``synth.generate_trial`` -- vary
    them to produce different swimmers/sessions:

    * ``n_lengths`` -- session length (4 = the standard T7)
    * ``stroke_period_s`` -- swim tempo, seconds/stroke (smaller = faster)
    * ``breathe_every_n_strokes`` -- 3 = bilateral (alternating sides),
      2 = unilateral (always the same side)
    * ``mount_slip_deg_per_min`` -- sensor slipping during the swim (> 0)
    * ``noise`` -- Movella DOT sensor noise/bias (False = clean round-trip)
    """
    from swimlab import calibrate, events, metrics, synth

    # Calibration shares the swimmer's mount/baseline and noise level so it
    # round-trips (a clean trial needs a clean calibration).
    segs, _ = synth.generate_calibration(
        mount_offset_deg=mount, pitch_baseline_deg=baseline, noise=noise, seed=seed + 7
    )
    R = calibrate.fit_transform(segs["t0a"], segs["t0b"])
    pose_flag = calibrate.pose_check(segs["t0a"], segs["t0b"])
    df, gt = synth.generate_trial(
        archetype, mount_offset_deg=mount, noise=noise, seed=seed,
        pitch_baseline_deg=baseline, n_lengths=n_lengths,
        stroke_period_s=stroke_period_s,
        breathe_every_n_strokes=breathe_every_n_strokes,
        mount_slip_deg_per_min=mount_slip_deg_per_min,
    )
    gt["mount_offset_deg"] = list(mount)
    gt["swimmer_id"] = f"{swimmer_id} (synthetic {archetype.lower()})"
    cal = calibrate.apply(df, R)
    breaths = events.detect_breath_windows(cal)
    pushoffs = events.detect_pushoffs(cal)
    marked = events.apply_exclusions(breaths, pushoffs, cal)
    pb = metrics.per_breath_metrics(cal, marked)
    summ = metrics.trial_summary(pb)
    flags = [f for f in [pose_flag] if f]
    if int(summ["n_valid"][0]) < 20:
        flags.append("INSUFFICIENT_CYCLES")
    return _attach_findings(_package(cal, gt, pb, summ, pushoffs, flags))


def add_narrative(payload: dict, model: str, lang: str = "en") -> dict:
    """Attach an LLM-generated interpretation (``payload["narrative"]``) in place.

    Deterministic analysis is already done; this only rewrites the *interpretation*
    layer, in ``lang`` ("en" default, "he" for Hebrew). Any failure (no key, no
    SDK, API/refusal error) is caught and the payload is returned unchanged, so
    the viewer falls back to its rule-based text.
    """
    import narrate
    try:
        payload["narrative"] = narrate.narrate_payload(payload, model=model, lang=lang)
        print(f"    narrated with {payload['narrative']['model']} ({lang})")
    except Exception as e:  # noqa: BLE001 - degrade gracefully, never block export
        print(f"    narration skipped ({e}); using rule-based text")
    return payload


def build_set(narrate_model: str | None = None, lang: str = "en") -> dict:
    """Run the prefab swimmers through the pipeline into a multi-session bundle
    (``{sessions: {label: payload}, default: label}``) for the viewer dropdown."""
    sessions = {}
    for label, arch, seed, baseline, mount, sid in _PREFAB:
        sessions[label] = from_mock(arch, seed, baseline, mount, swimmer_id=sid)
        s = sessions[label]["summary"]
        print(f"  {label:20s} pattern={sessions[label]['detected_pattern']:8s} "
              f"mean_d_pitch={s['mean_d_pitch_breath']:5.1f}°  "
              f"valid={s['n_valid']}/{s['n_breaths']}  "
              f"flags={sessions[label]['flags'] or 'none'}")
        if narrate_model:
            add_narrative(sessions[label], narrate_model, lang=lang)
    return {"sessions": sessions, "default": _PREFAB[0][0]}


# --------------------------------------------------------------------------- #
# Sacrum (pelvis) placement export -- the second viewer module
# --------------------------------------------------------------------------- #

# Prefab swimmers for the sacrum viewer. Each carries its own body-roll amplitude
# and a small L/R imbalance so the symmetry metric shows real variety.
# (label, archetype, seed, mount, swimmer_id, body_roll_amp_deg, roll_asymmetry_frac)
_SACRUM_PREFAB = [
    ("Rotator · S-02", "ROTATOR", 100, (-6.0, 5.0, 14.0), "S-02", 52.0, 0.04),
    ("Lifter · S-01", "LIFTER", 100, (4.0, -3.0, 11.0), "S-01", 40.0, 0.10),
    ("Mixed · S-03", "MIXED", 100, (8.0, -4.0, 9.0), "S-03", 46.0, 0.18),
    ("Asymmetric · S-04", "ASYMMETRIC", 100, (2.0, 7.0, 13.0), "S-04", 48.0, 0.28),
    ("Flat · S-05", "FLAT", 100, (-3.0, -6.0, 16.0), "S-05", 44.0, 0.06),
]


def sacrum_from_mock(
    archetype: str,
    seed: int,
    mount: tuple[float, float, float],
    swimmer_id: str = "S-01",
    *,
    body_roll_amp_deg: float = 48.0,
    roll_asymmetry_frac: float = 0.0,
    pool_length_m: float = 25.0,
    n_lengths: int = 4,
    noise: bool = True,
) -> dict:
    """Synthesise a swimmer body and run its sacrum sensor through the pipeline.

    Mirrors :func:`from_mock` for the head, but on the pelvis: one
    ``synth.generate_swim`` body, a virtual sacrum sensor, calibrated against a
    matched upright+prone pose pair (:func:`synth.generate_calibration` at the
    pelvis baseline), through ``sacrum.calibrate -> detect_events -> metrics``.
    Distance is ``lengths x pool_length_m`` -- an IMU cannot measure position.
    """
    from swimlab import sacrum, synth

    body = synth.generate_swim(
        archetype, seed=seed, pitch_baseline_deg=4.0, n_lengths=n_lengths,
        body_roll_amp_deg=body_roll_amp_deg, roll_asymmetry_frac=roll_asymmetry_frac,
        pool_length_m=pool_length_m,
    )
    trial, _ = synth.virtual_sensor(body, "sacrum", mount_offset_deg=mount, noise=noise, seed=seed)
    segs, _ = synth.generate_calibration(
        mount_offset_deg=mount, pitch_baseline_deg=body.meta["pelvis_baseline_deg"],
        noise=noise, seed=seed + 7,
    )
    R = sacrum.calibrate_transform(segs["t0a"], segs["t0b"])
    pose_flag = sacrum.pose_check(segs["t0a"], segs["t0b"])
    cal = sacrum.apply(trial, R)
    ev = sacrum.detect_events(cal, trial)
    m = sacrum.metrics(cal, ev, pool_length_m=pool_length_m)

    row = m.row(0, named=True)
    flags = list(row.get("flags") or [])
    if pose_flag:
        flags.append(pose_flag)

    t = cal["t"].to_numpy()
    roll = cal["roll_deg"].to_numpy()
    step = max(1, len(t) // 1500)

    strokes = [
        {
            "t_peak": _trim(s["t_peak"], 2),
            "side": s["side"],
            "peak_roll_deg": _trim(s["peak_roll_deg"], 1),
            "length_index": s["length_index"],
            "excluded": bool(s["excluded"]),
        }
        for s in ev["strokes"].iter_rows(named=True)
    ]
    lengths = []
    for lr in ev["lengths"].iter_rows(named=True):
        li = lr["length_index"]
        n_str = sum(1 for s in strokes if s["length_index"] == li and not s["excluded"])
        lengths.append(
            {
                "length_index": li,
                "t_start": _trim(lr["t_start"], 2),
                "t_end": _trim(lr["t_end"], 2),
                "duration_s": _trim(lr["duration_s"], 2),
                "strokes": n_str,
            }
        )

    return _attach_findings({
        "placement": "sacrum",
        "swimmer_id": f"{swimmer_id} (synthetic {archetype.lower()})",
        "session": "T7 — 4×25 m front crawl",
        "pool_length_m": pool_length_m,
        "mount_offset_deg": [_trim(v, 1) for v in mount],
        "archetype": archetype,
        "summary": {
            "lengths": row["lengths"],
            "distance_m": _trim(row["distance_m"], 1),
            "stroke_count": row["stroke_count"],
            "n_valid_strokes": row["n_valid_strokes"],
            "tempo_spm": _trim(row["tempo_spm"], 1),
            "stroke_rate_cpm": _trim(row["stroke_rate_cpm"], 1),
            "mean_stroke_period_s": _trim(row["mean_stroke_period_s"], 2),
            "body_roll_amplitude_deg": _trim(row["body_roll_amplitude_deg"], 1),
            "mean_peak_roll_right_deg": _trim(row["mean_peak_roll_right_deg"], 1),
            "mean_peak_roll_left_deg": _trim(row["mean_peak_roll_left_deg"], 1),
            "roll_symmetry_index": _trim(row["roll_symmetry_index"], 3),
            "pushoff_count": row["pushoff_count"],
            "mean_pushoff_interval_s": _trim(row["mean_pushoff_interval_s"], 2),
            "pace_drift_s_per_length": _trim(row["pace_drift_s_per_length"], 3),
        },
        "flags": sorted(set(flags)),
        "lengths": lengths,
        "strokes": strokes,
        "pushoffs": [_trim(x, 2) for x in ev["pushoffs"]["t_peak"].to_numpy()]
        if "t_peak" in ev["pushoffs"].columns else [],
        "traces": {
            "t": [_trim(x, 3) for x in t[::step]],
            "roll": [_trim(x, 1) for x in roll[::step]],
        },
    })


def build_sacrum_set() -> dict:
    """Run the prefab swimmers' sacrum sensors into a multi-session bundle."""
    sessions = {}
    for label, arch, seed, mount, sid, amp, asym in _SACRUM_PREFAB:
        sessions[label] = sacrum_from_mock(
            arch, seed, mount, swimmer_id=sid,
            body_roll_amp_deg=amp, roll_asymmetry_frac=asym,
        )
        s = sessions[label]["summary"]
        print(f"  {label:20s} lengths={s['lengths']} strokes={s['stroke_count']} "
              f"tempo={s['tempo_spm']}spm roll={s['body_roll_amplitude_deg']}° "
              f"sym={s['roll_symmetry_index']}  flags={sessions[label]['flags'] or 'none'}")
    return {"sessions": sessions, "default": _SACRUM_PREFAB[0][0]}


# --------------------------------------------------------------------------- #
# Wrist (forearm) placement export -- L + R + symmetry
# --------------------------------------------------------------------------- #

# (label, archetype, seed, mount, swimmer_id, arm_asymmetry_frac)
_WRIST_PREFAB = [
    ("Rotator · S-02", "ROTATOR", 100, (-6.0, 5.0, 14.0), "S-02", 0.03),
    ("Lifter · S-01", "LIFTER", 100, (4.0, -3.0, 11.0), "S-01", 0.10),
    ("Mixed · S-03", "MIXED", 100, (8.0, -4.0, 9.0), "S-03", 0.20),
    ("Asymmetric · S-04", "ASYMMETRIC", 100, (2.0, 7.0, 13.0), "S-04", 0.30),
    ("Flat · S-05", "FLAT", 100, (-3.0, -6.0, 16.0), "S-05", 0.05),
]


def _wrist_arm_payload(body, side: str, mount, seed: int, noise: bool) -> dict:
    """Run one forearm sensor through the wrist pipeline -> a compact arm block."""
    from swimlab import synth, wrist

    placement = {"R": "wrist_r", "L": "wrist_l"}[side]
    trial, _ = synth.virtual_sensor(body, placement, mount_offset_deg=mount, noise=noise, seed=seed)
    segs, _ = synth.generate_calibration(
        mount_offset_deg=mount, pitch_baseline_deg=body.meta["forearm_baseline_deg"],
        noise=noise, seed=seed + 7,
    )
    R = wrist.calibrate_transform(segs["t0a"], segs["t0b"])
    cal = wrist.apply(trial, R)
    ev = wrist.detect_events(cal, trial)
    m = wrist.metrics(cal, ev, side=side)
    row = m.row(0, named=True)

    t = cal["t"].to_numpy()
    pitch = cal["pitch_deg"].to_numpy()
    step = max(1, len(t) // 1200)
    strokes = [
        {
            "t_catch": _trim(s["t_catch"], 2),
            "t_pull": _trim(s["t_pull"], 2),
            "t_exit": _trim(s["t_exit"], 2),
            "min_pitch_deg": _trim(s["min_pitch_deg"], 1),
            "excluded": bool(s["excluded"]),
        }
        for s in ev["strokes"].iter_rows(named=True)
    ]
    return {
        "summary": {
            "stroke_count": row["stroke_count"],
            "n_valid_strokes": row["n_valid_strokes"],
            "stroke_rate_cpm": _trim(row["stroke_rate_cpm"], 1),
            "mean_cycle_s": _trim(row["mean_cycle_s"], 2),
            "mean_pull_duration_s": _trim(row["mean_pull_duration_s"], 2),
            "mean_recovery_duration_s": _trim(row["mean_recovery_duration_s"], 2),
            "pull_fraction": _trim(row["pull_fraction"], 3),
            "pitch_amplitude_deg": _trim(row["pitch_amplitude_deg"], 1),
        },
        "flags": sorted(row.get("flags") or []),
        "strokes": strokes,
        "traces": {
            "t": [_trim(x, 3) for x in t[::step]],
            "pitch": [_trim(x, 1) for x in pitch[::step]],
        },
        "_ev": ev,  # kept only to compute symmetry; stripped before serialising
    }


def wrist_from_mock(
    archetype: str, seed: int, mount: tuple[float, float, float], swimmer_id: str = "S-01",
    *, arm_asymmetry_frac: float = 0.0, noise: bool = True,
) -> dict:
    """Both forearm sensors from one body + the L/R symmetry fusion metric."""
    from swimlab import synth, wrist

    body = synth.generate_swim(
        archetype, seed=seed, pitch_baseline_deg=4.0, arm_asymmetry_frac=arm_asymmetry_frac
    )
    arms = {s: _wrist_arm_payload(body, s, mount, seed, noise) for s in ("R", "L")}
    from swimlab import wrist as _w  # metrics frames for symmetry()
    mR = _pl_from_arm(arms["R"]); mL = _pl_from_arm(arms["L"])
    sym = _w.symmetry(mR, mL, arms["R"].pop("_ev"), arms["L"].pop("_ev")).row(0, named=True)
    return _attach_findings({
        "placement": "wrist",
        "swimmer_id": f"{swimmer_id} (synthetic {archetype.lower()})",
        "session": "T7 — 4×25 m front crawl",
        "mount_offset_deg": [_trim(v, 1) for v in mount],
        "archetype": archetype,
        "arms": arms,
        "symmetry": {k: _trim(v, 3) for k, v in sym.items()},
        "flags": sorted(set(arms["R"]["flags"]) | set(arms["L"]["flags"])),
    })


def _pl_from_arm(arm: dict):
    """A one-row polars frame of an arm's summary, for wrist.symmetry()."""
    import polars as pl
    s = arm["summary"]
    return pl.DataFrame([{
        "side": None,
        "stroke_count": s["stroke_count"],
        "n_valid_strokes": s["n_valid_strokes"],
        "stroke_rate_cpm": s["stroke_rate_cpm"],
        "mean_cycle_s": s["mean_cycle_s"],
        "mean_pull_duration_s": s["mean_pull_duration_s"],
        "mean_recovery_duration_s": s["mean_recovery_duration_s"],
        "pull_fraction": s["pull_fraction"],
        "pitch_amplitude_deg": s["pitch_amplitude_deg"],
        "mean_min_pitch_deg": None,
        "flags": arm["flags"],
    }])


def build_wrist_set() -> dict:
    """Prefab swimmers' wrist (L+R+symmetry) into a multi-session bundle."""
    sessions = {}
    for label, arch, seed, mount, sid, asym in _WRIST_PREFAB:
        sessions[label] = wrist_from_mock(arch, seed, mount, swimmer_id=sid, arm_asymmetry_frac=asym)
        sy = sessions[label]["symmetry"]
        rR = sessions[label]["arms"]["R"]["summary"]; rL = sessions[label]["arms"]["L"]["summary"]
        print(f"  {label:20s} R:{rR['stroke_count']}str/{rR['pitch_amplitude_deg']}° "
              f"L:{rL['stroke_count']}str/{rL['pitch_amplitude_deg']}° "
              f"amp_sym={sy['amplitude_symmetry_index']} phase={sy['mean_phase_offset_cycles']}")
    return {"sessions": sessions, "default": _WRIST_PREFAB[0][0]}


def build_app_bundle() -> dict:
    """One bundle for the holistic app: head + sacrum + wrist prefab sets.

    Shape: ``{placements: {head, sacrum, wrist}, default_placement}``. Each
    placement value is a ``{sessions, default}`` bundle the app renders per its
    placement type. Head reuses the (un-narrated) head set.
    """
    print("head set:")
    head = build_set(narrate_model=None)
    print("sacrum set:")
    sacrum_b = build_sacrum_set()
    print("wrist set:")
    wrist_b = build_wrist_set()
    return {
        "placements": {"head": head, "sacrum": sacrum_b, "wrist": wrist_b},
        "default_placement": "sacrum",
    }


def from_session(path: Path) -> dict:
    """Read a real session directory via swimlab's run_session (io.py path)."""
    raise NotImplementedError(
        "Real-session export is blocked until swimlab/io.py can read a Movella DOT "
        "export. Use --mock for now; wire this to swimlab.pipeline.run_session once "
        "the reader lands."
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--mock", metavar="ARCHETYPE",
                     help="synthesise one swimmer: LIFTER|ROTATOR|MIXED|FLAT|ASYMMETRIC")
    src.add_argument("--set", action="store_true",
                     help="build the prefab multi-swimmer bundle for the dropdown")
    src.add_argument("--sacrum-set", action="store_true",
                     help="build the prefab sacrum (pelvis) bundle for the sacrum viewer")
    src.add_argument("--wrist-set", action="store_true",
                     help="build the prefab wrist (forearm L+R+symmetry) bundle")
    src.add_argument("--app-bundle", action="store_true",
                     help="build the combined head+sacrum+wrist bundle for the holistic app")
    src.add_argument("--session", type=Path, help="a real session directory (blocked)")
    ap.add_argument("--seed", type=int, default=100,
                    help="a different individual of the archetype (re-rolls everything)")
    ap.add_argument("--baseline", type=float, default=5.0,
                    help="prone head pitch, deg (-5..12 realistic)")
    ap.add_argument("--mount", type=float, nargs=3, default=(4.0, -3.0, 11.0),
                    metavar=("X", "Y", "Z"), help="sensor mount offset, deg")
    ap.add_argument("--n-lengths", type=int, default=4, help="session length (4 = T7)")
    ap.add_argument("--stroke-period", type=float, default=1.4,
                    help="swim tempo, seconds/stroke (smaller = faster)")
    ap.add_argument("--breathe-every", type=int, default=3,
                    help="breathe every N strokes: 3 = bilateral, 2 = unilateral")
    ap.add_argument("--mount-slip", type=float, default=0.0,
                    help="sensor slip during the swim, deg/min")
    ap.add_argument("--clean", action="store_true",
                    help="no sensor noise (a clean round-trip)")
    ap.add_argument("--narrate", action="store_true",
                    help="generate the summary/corrections/drills with Claude "
                         "(needs ANTHROPIC_API_KEY; falls back to rule-based text)")
    ap.add_argument("--narrate-model", default="claude-opus-5",
                    help="model id for --narrate (default: claude-opus-5)")
    ap.add_argument("--lang", default="en", choices=["en", "he"],
                    help="language for --narrate prose (default: en; he = Hebrew)")
    ap.add_argument("--out", type=Path, default=Path("data.json"))
    args = ap.parse_args()
    narrate_model = args.narrate_model if args.narrate else None

    if args.set:
        print("building prefab swimmer set:")
        payload = build_set(narrate_model=narrate_model, lang=args.lang)
        args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote {args.out} — {len(payload['sessions'])} swimmers")
        return

    if args.sacrum_set:
        print("building prefab sacrum set:")
        payload = build_sacrum_set()
        args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote {args.out} — {len(payload['sessions'])} sacrum sessions")
        return

    if args.wrist_set:
        print("building prefab wrist set:")
        payload = build_wrist_set()
        args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote {args.out} — {len(payload['sessions'])} wrist sessions")
        return

    if args.app_bundle:
        print("building holistic app bundle:")
        payload = build_app_bundle()
        args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        n = {k: len(v["sessions"]) for k, v in payload["placements"].items()}
        print(f"wrote {args.out} — placements {n}")
        return

    if args.mock:
        payload = from_mock(
            args.mock.upper(), args.seed, args.baseline, tuple(args.mount),
            n_lengths=args.n_lengths, stroke_period_s=args.stroke_period,
            breathe_every_n_strokes=args.breathe_every,
            mount_slip_deg_per_min=args.mount_slip, noise=not args.clean,
        )
        if narrate_model:
            add_narrative(payload, narrate_model, lang=args.lang)
    else:
        payload = from_session(args.session)

    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {args.out} — pattern={payload['detected_pattern']} "
          f"mean_d_pitch={payload['summary']['mean_d_pitch_breath']}° "
          f"flags={payload['flags'] or 'none'}")


if __name__ == "__main__":
    main()
