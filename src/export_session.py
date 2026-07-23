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
_GATE_THRESHOLD_DEG = 13.5  # lifter/rotator separation from the integration gate


def _trim(x: float, d: int = 2) -> float:
    return round(float(x), d)


def _package(cal, gt, pb, summ, pushoffs, flags) -> dict:
    """Assemble the viewer payload from pipeline outputs."""
    t = cal["t"].to_numpy()
    pitch = cal["pitch_deg"].to_numpy()
    roll = cal["roll_deg"].to_numpy()
    step = max(1, len(t) // 3500)  # keep the payload light for the browser

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

    mean_dpitch = float(summ["mean_d_pitch_breath"][0])
    return {
        "swimmer_id": gt.get("swimmer_id", "S-01 (synthetic)"),
        "session": "T7 — 4×25 m front crawl, breathing every 3",
        "mount_offset_deg": [_trim(v, 1) for v in gt.get("mount_offset_deg", [0, 0, 0])],
        "detected_pattern": "Lifter" if mean_dpitch > _GATE_THRESHOLD_DEG else "Rotator",
        "gate_threshold_deg": _GATE_THRESHOLD_DEG,
        "summary": {
            "mean_d_pitch_breath": _trim(mean_dpitch),
            "pitch_variability": _trim(float(summ["pitch_variability"][0])),
            "asymmetry_index": _trim(float(summ["asymmetry_index"][0]), 3),
            "mean_peak_roll_breath": _trim(float(summ["mean_peak_roll_breath"][0]), 1),
            "mean_roll_pitch_ratio": _trim(float(summ["mean_roll_pitch_ratio"][0]), 3),
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
            "apex_roll": _trim(float(summ["mean_peak_roll_breath"][0]), 1),
        },
    }


def from_mock(archetype: str, seed: int, baseline: float,
              mount: tuple[float, float, float]) -> dict:
    """Synthesise a swimmer and run it through the pipeline (no hardware)."""
    from swimlab import calibrate, events, metrics, synth

    segs, _ = synth.generate_calibration(
        mount_offset_deg=mount, pitch_baseline_deg=baseline, noise=True, seed=seed + 7
    )
    R = calibrate.fit_transform(segs["t0a"], segs["t0b"])
    pose_flag = calibrate.pose_check(segs["t0a"], segs["t0b"])
    df, gt = synth.generate_trial(
        archetype, mount_offset_deg=mount, noise=True, seed=seed,
        pitch_baseline_deg=baseline,
    )
    gt["mount_offset_deg"] = list(mount)
    cal = calibrate.apply(df, R)
    breaths = events.detect_breath_windows(cal)
    pushoffs = events.detect_pushoffs(cal)
    marked = events.apply_exclusions(breaths, pushoffs, cal)
    pb = metrics.per_breath_metrics(cal, marked)
    summ = metrics.trial_summary(pb)
    flags = [f for f in [pose_flag] if f]
    if int(summ["n_valid"][0]) < 20:
        flags.append("INSUFFICIENT_CYCLES")
    return _package(cal, gt, pb, summ, pushoffs, flags)


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
                     help="synthesise a swimmer: LIFTER|ROTATOR|MIXED|FLAT|ASYMMETRIC")
    src.add_argument("--session", type=Path, help="a real session directory (blocked)")
    ap.add_argument("--seed", type=int, default=100)
    ap.add_argument("--baseline", type=float, default=5.0, help="prone head pitch, deg")
    ap.add_argument("--mount", type=float, nargs=3, default=(4.0, -3.0, 11.0))
    ap.add_argument("--out", type=Path, default=Path("data.json"))
    args = ap.parse_args()

    if args.mock:
        payload = from_mock(args.mock.upper(), args.seed, args.baseline, tuple(args.mount))
    else:
        payload = from_session(args.session)

    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {args.out} — pattern={payload['detected_pattern']} "
          f"mean_d_pitch={payload['summary']['mean_d_pitch_breath']}° "
          f"flags={payload['flags'] or 'none'}")


if __name__ == "__main__":
    main()
