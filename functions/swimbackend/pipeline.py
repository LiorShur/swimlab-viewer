"""Backend processing core: Movella DOT recordings -> dashboard payloads.

This is the server-side heart of the app (Phase A). It takes **Custom Mode 5**
recordings (raw Acceleration + Quaternion + Angular velocity CSVs -- exactly what
``swimlab.io.write_dot_export`` produces and a real DOT records) for one or more
sensor placements, runs the **validated ``swimlab`` engine** (calibrate -> events
-> metrics + fusion), and returns the same JSON payloads the dashboards already
render. It is pure Python -- **no Firebase imports** -- so it is unit-testable in
place and reused by the Cloud Function handlers in ``functions/main.py``.

Nothing here re-derives a metric: every number comes from ``swimlab``. The
rule-based ``findings`` and the payload shapes mirror ``src/export_session.py`` so
a real recording and a synthetic one produce identical dashboards.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from swimlab import calibrate, events, io, metrics, sacrum, wrist

from . import findings

_GATE_THRESHOLD_DEG = 13.5  # lifter/rotator gate (mirrors export_session)
_REFERENCE_APEX = {"apex_pitch": 4.0, "apex_roll": 68.0}


def _trim(x, d: int = 2):
    return None if x is None else round(float(x), d)


def _read_csv(text: str):
    """Read a DOT CSV (text) into the canonical dataframe via the validated reader."""
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as fh:
        fh.write(text)
        path = fh.name
    try:
        return io.read_dot_export(path)
    finally:
        Path(path).unlink(missing_ok=True)


# Single-file capture: the calibration poses are held at the START of the one
# recording. This split is PROVISIONAL and locked once a real DOT export exists.
_SINGLE_FILE_CAL_WINDOW_S = 10.0  # first N s = the two calibration poses  # TODO(real-file)


def _calib_frames(rec: dict):
    """Return ``(trial, t0a, t0b, extra_flags)`` for a recording, supporting two
    capture shapes:

    * **Calibration set** — ``rec`` has ``trial`` + ``t0a`` + ``t0b`` (the
      validated path): read all three as-is.
    * **Single file** — ``rec`` has only ``trial``: take the first
      ``_SINGLE_FILE_CAL_WINDOW_S`` seconds as the two calibration poses (first
      half T0a, second half T0b) and the remainder as the swim, re-zeroed.
      Emits ``CALIB_FROM_TRIAL_PROVISIONAL`` so the approximation is never
      silently trusted. Window/pose-order are ``# TODO(real-file)``.
    """
    trial = _read_csv(rec["trial"])
    if rec.get("t0a") and rec.get("t0b"):
        return trial, _read_csv(rec["t0a"]), _read_csv(rec["t0b"]), []
    t0 = float(trial["t"].min())
    win = _SINGLE_FILE_CAL_WINDOW_S
    cal = trial.filter(pl.col("t") < t0 + win)
    half = t0 + win / 2.0
    t0a = cal.filter(pl.col("t") < half)
    t0b = cal.filter(pl.col("t") >= half)
    swim = trial.filter(pl.col("t") >= t0 + win)
    if min(t0a.height, t0b.height) < 2 or swim.height < 2:
        raise ValueError(
            "single-file recording too short to split off a "
            f"{win:g}s calibration window — provide T0a/T0b, or a longer file")
    swim = swim.with_columns(pl.col("t") - float(swim["t"].min()))  # re-zero to 0
    return swim, t0a, t0b, ["CALIB_FROM_TRIAL_PROVISIONAL"]


def _meta(rec: dict, default_session: str) -> dict:
    return {
        "swimmer_id": rec.get("swimmer_id", "Swimmer"),
        "session": rec.get("session", default_session),
        "mount_offset_deg": rec.get("mount_offset_deg", [0.0, 0.0, 0.0]),
        "archetype": rec.get("archetype", ""),
    }


# --------------------------------------------------------------------------- #
# Head (skull)
# --------------------------------------------------------------------------- #


def process_head(rec: dict) -> dict:
    """One head recording (+ its T0a/T0b calibration poses) -> head payload."""
    trial, t0a, t0b, xflags = _calib_frames(rec)
    R = calibrate.fit_transform(t0a, t0b)
    pose_flag = calibrate.pose_check(t0a, t0b)
    cal = calibrate.apply(trial, R)
    pushoffs = events.detect_pushoffs(trial)
    breaths = events.apply_exclusions(events.detect_breath_windows(cal), pushoffs, cal)
    pb = metrics.per_breath_metrics(cal, breaths)
    summ = metrics.trial_summary(pb)

    flags = [f for f in [pose_flag] if f] + xflags
    if int(summ["n_valid"][0]) < 20:
        flags.append("INSUFFICIENT_CYCLES")

    t = cal["t"].to_numpy()
    pitch = cal["pitch_deg"].to_numpy()
    roll = cal["roll_deg"].to_numpy()
    step = max(1, len(t) // 1500)
    breaths_out = [
        {k: (_trim(v) if isinstance(v, float) else v) for k, v in r.items()
         if k in ("t_start", "t_end", "side", "d_pitch_breath", "peak_roll_breath",
                  "roll_pitch_ratio", "breath_duration", "excluded", "exclusion_reason")}
        for r in pb.iter_rows(named=True)
    ]
    md = summ["mean_d_pitch_breath"][0]
    mean_dpitch = 0.0 if md is None else float(md)
    m = _meta(rec, "T7 — 4×25 m front crawl, breathing every 3")
    payload = {
        "placement": "head",
        "swimmer_id": m["swimmer_id"], "session": m["session"],
        "mount_offset_deg": [_trim(v, 1) for v in m["mount_offset_deg"]],
        "archetype": m["archetype"],
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
        "flags": sorted(set(flags)),
        "breaths": breaths_out,
        "traces": {"t": [_trim(x, 3) for x in t[::step]],
                   "pitch": [_trim(x) for x in pitch[::step]],
                   "roll": [_trim(x) for x in roll[::step]]},
        "pushoffs": [_trim(x) for x in pushoffs["t_peak"].to_numpy()]
        if "t_peak" in pushoffs.columns else [],
        "reference": _REFERENCE_APEX,
        "observed_apex": {"apex_pitch": _trim(mean_dpitch, 1),
                          "apex_roll": _trim(summ["mean_peak_roll_breath"][0], 1)},
    }
    payload["findings"] = findings.findings_for(payload)
    return payload


# --------------------------------------------------------------------------- #
# Sacrum (pelvis)
# --------------------------------------------------------------------------- #


def process_sacrum(rec: dict, *, pool_length_m: float = 25.0) -> dict:
    trial, t0a, t0b, xflags = _calib_frames(rec)
    R = sacrum.calibrate_transform(t0a, t0b)
    pose_flag = sacrum.pose_check(t0a, t0b)
    cal = sacrum.apply(trial, R)
    ev = sacrum.detect_events(cal, trial)
    mrow = sacrum.metrics(cal, ev, pool_length_m=pool_length_m).row(0, named=True)

    flags = list(mrow.get("flags") or []) + xflags
    if pose_flag:
        flags.append(pose_flag)

    t = cal["t"].to_numpy()
    roll = cal["roll_deg"].to_numpy()
    step = max(1, len(t) // 1500)
    strokes = [{"t_peak": _trim(s["t_peak"], 2), "side": s["side"],
                "peak_roll_deg": _trim(s["peak_roll_deg"], 1),
                "length_index": s["length_index"], "excluded": bool(s["excluded"])}
               for s in ev["strokes"].iter_rows(named=True)]
    lengths = []
    for lr in ev["lengths"].iter_rows(named=True):
        li = lr["length_index"]
        n_str = sum(1 for s in strokes if s["length_index"] == li and not s["excluded"])
        lengths.append({"length_index": li, "t_start": _trim(lr["t_start"], 2),
                        "t_end": _trim(lr["t_end"], 2), "duration_s": _trim(lr["duration_s"], 2),
                        "strokes": n_str})
    m = _meta(rec, "T7 — 4×25 m front crawl")
    payload = {
        "placement": "sacrum",
        "swimmer_id": m["swimmer_id"], "session": m["session"], "pool_length_m": pool_length_m,
        "mount_offset_deg": [_trim(v, 1) for v in m["mount_offset_deg"]], "archetype": m["archetype"],
        "summary": {
            "lengths": mrow["lengths"], "distance_m": _trim(mrow["distance_m"], 1),
            "stroke_count": mrow["stroke_count"], "n_valid_strokes": mrow["n_valid_strokes"],
            "tempo_spm": _trim(mrow["tempo_spm"], 1), "stroke_rate_cpm": _trim(mrow["stroke_rate_cpm"], 1),
            "mean_stroke_period_s": _trim(mrow["mean_stroke_period_s"], 2),
            "body_roll_amplitude_deg": _trim(mrow["body_roll_amplitude_deg"], 1),
            "mean_peak_roll_right_deg": _trim(mrow["mean_peak_roll_right_deg"], 1),
            "mean_peak_roll_left_deg": _trim(mrow["mean_peak_roll_left_deg"], 1),
            "roll_symmetry_index": _trim(mrow["roll_symmetry_index"], 3),
            "pushoff_count": mrow["pushoff_count"],
            "mean_pushoff_interval_s": _trim(mrow["mean_pushoff_interval_s"], 2),
            "pace_drift_s_per_length": _trim(mrow["pace_drift_s_per_length"], 3),
        },
        "flags": sorted(set(flags)), "lengths": lengths, "strokes": strokes,
        "pushoffs": [_trim(x, 2) for x in ev["pushoffs"]["t_peak"].to_numpy()]
        if "t_peak" in ev["pushoffs"].columns else [],
        "traces": {"t": [_trim(x, 3) for x in t[::step]], "roll": [_trim(x, 1) for x in roll[::step]]},
    }
    payload["findings"] = findings.findings_for(payload)
    return payload


# --------------------------------------------------------------------------- #
# Wrist (forearm L + R, fused)
# --------------------------------------------------------------------------- #


def _wrist_arm(rec: dict, side: str) -> tuple[dict, dict, Any]:
    trial, t0a, t0b, xflags = _calib_frames(rec)
    R = wrist.calibrate_transform(t0a, t0b)
    cal = wrist.apply(trial, R)
    ev = wrist.detect_events(cal, trial)
    mdf = wrist.metrics(cal, ev, side=side)
    row = mdf.row(0, named=True)
    t = cal["t"].to_numpy()
    pitch = cal["pitch_deg"].to_numpy()
    step = max(1, len(t) // 1200)
    strokes = [{"t_catch": _trim(s["t_catch"], 2), "t_pull": _trim(s["t_pull"], 2),
                "t_exit": _trim(s["t_exit"], 2), "min_pitch_deg": _trim(s["min_pitch_deg"], 1),
                "excluded": bool(s["excluded"])}
               for s in ev["strokes"].iter_rows(named=True)]
    arm = {
        "summary": {
            "stroke_count": row["stroke_count"], "n_valid_strokes": row["n_valid_strokes"],
            "stroke_rate_cpm": _trim(row["stroke_rate_cpm"], 1), "mean_cycle_s": _trim(row["mean_cycle_s"], 2),
            "mean_pull_duration_s": _trim(row["mean_pull_duration_s"], 2),
            "mean_recovery_duration_s": _trim(row["mean_recovery_duration_s"], 2),
            "pull_fraction": _trim(row["pull_fraction"], 3),
            "pitch_amplitude_deg": _trim(row["pitch_amplitude_deg"], 1),
        },
        "flags": sorted(set((row.get("flags") or []) + xflags)), "strokes": strokes,
        "traces": {"t": [_trim(x, 3) for x in t[::step]], "pitch": [_trim(x, 1) for x in pitch[::step]]},
    }
    return arm, row, ev


def process_wrist(rec_l: dict, rec_r: dict) -> dict:
    import polars as pl

    armL, rowL, evL = _wrist_arm(rec_l, "L")
    armR, rowR, evR = _wrist_arm(rec_r, "R")
    mL = pl.DataFrame([{**rowL, "side": "L"}])
    mR = pl.DataFrame([{**rowR, "side": "R"}])
    sym = wrist.symmetry(mR, mL, evR, evL).row(0, named=True)
    m = _meta(rec_r, "T7 — 4×25 m front crawl")
    payload = {
        "placement": "wrist",
        "swimmer_id": m["swimmer_id"], "session": m["session"],
        "mount_offset_deg": [_trim(v, 1) for v in m["mount_offset_deg"]], "archetype": m["archetype"],
        "arms": {"R": armR, "L": armL},
        "symmetry": {k: _trim(v, 3) for k, v in sym.items()},
        "flags": sorted(set(armR["flags"]) | set(armL["flags"])),
    }
    payload["findings"] = findings.findings_for(payload)
    return payload


def _single_wrist_findings(side: str, amp, rate) -> dict:
    """A minimal bilingual finding when only one wrist was recorded (no L/R
    symmetry to report). Keeps the 'never silently drop data' promise."""
    name = {"R": "right", "L": "left"}[side]
    he_name = {"R": "ימין", "L": "שמאל"}[side]
    return {
        "placement": "wrist",
        "en": {
            "headline": f"{name.capitalize()} forearm",
            "summary": (f"Only the {name} wrist was recorded — stroke rate "
                        f"{rate}/min, forearm pitch range {amp}°. Add the other "
                        f"wrist to compare left/right symmetry."),
            "coaching": [],
        },
        "he": {
            "headline": f"אמה {he_name}",
            "summary": (f"נרשמה רק יד {he_name} — קצב תנועות {rate} לדקה, טווח "
                        f"פיץ׳ אמה {amp}°. הוסף את פרק היד השני כדי להשוות "
                        f"סימטריית ימין/שמאל."),
            "coaching": [],
        },
    }


def process_wrist_single(rec: dict, side: str) -> dict:
    """One wrist only -> a single-arm wrist payload (no fusion/symmetry)."""
    arm, _row, _ev = _wrist_arm(rec, side)
    m = _meta(rec, "T7 — 4×25 m front crawl")
    payload = {
        "placement": "wrist",
        "swimmer_id": m["swimmer_id"], "session": m["session"],
        "mount_offset_deg": [_trim(v, 1) for v in m["mount_offset_deg"]], "archetype": m["archetype"],
        "arms": {side: arm},
        "single_arm": side,
        "flags": sorted(set(arm["flags"]) | {"SINGLE_WRIST"}),
    }
    payload["findings"] = _single_wrist_findings(
        side, arm["summary"]["pitch_amplitude_deg"], arm["summary"]["stroke_rate_cpm"])
    return payload


# --------------------------------------------------------------------------- #
# Session orchestration
# --------------------------------------------------------------------------- #


def process_session(recordings: list[dict], *, pool_length_m: float = 25.0) -> dict:
    """Process a swim's recordings (1..N placements) into the dashboard bundle.

    ``recordings`` is a list of ``{placement_id, trial, t0a, t0b, ...}`` (each
    value a Custom-Mode-5 CSV string). ``wrist_l`` + ``wrist_r`` are fused into a
    single ``wrist`` payload. Returns the app-bundle shape:
    ``{"placements": {"head": {"sessions": {label: payload}, "default": label}, ...},
       "default_placement": ...}``.
    """
    by = {r["placement_id"]: r for r in recordings}
    placements: dict[str, dict] = {}
    label = recordings[0].get("swimmer_id", "Swim") if recordings else "Swim"

    def _bundle(payload: dict) -> dict:
        return {"sessions": {label: payload}, "default": label}

    if "head" in by:
        placements["head"] = _bundle(process_head(by["head"]))
    if "sacrum" in by:
        placements["sacrum"] = _bundle(process_sacrum(by["sacrum"], pool_length_m=pool_length_m))
    if "wrist_l" in by and "wrist_r" in by:
        placements["wrist"] = _bundle(process_wrist(by["wrist_l"], by["wrist_r"]))
    elif "wrist_l" in by or "wrist_r" in by:  # one wrist only — don't drop it
        side_key = "wrist_l" if "wrist_l" in by else "wrist_r"
        placements["wrist"] = _bundle(process_wrist_single(by[side_key], side_key[-1].upper()))

    default_placement = ("sacrum" if "sacrum" in placements
                         else next(iter(placements), None))
    return {"placements": placements, "default_placement": default_placement}
