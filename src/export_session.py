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
    return _package(cal, gt, pb, summ, pushoffs, flags)


def add_narrative(payload: dict, model: str) -> dict:
    """Attach an LLM-generated interpretation (``payload["narrative"]``) in place.

    Deterministic analysis is already done; this only rewrites the *interpretation*
    layer. Any failure (no key, no SDK, API/refusal error) is caught and the
    payload is returned unchanged, so the viewer falls back to its rule-based text.
    """
    import narrate
    try:
        payload["narrative"] = narrate.narrate_payload(payload, model=model)
        print(f"    narrated with {payload['narrative']['model']}")
    except Exception as e:  # noqa: BLE001 - degrade gracefully, never block export
        print(f"    narration skipped ({e}); using rule-based text")
    return payload


def build_set(narrate_model: str | None = None) -> dict:
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
            add_narrative(sessions[label], narrate_model)
    return {"sessions": sessions, "default": _PREFAB[0][0]}


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
    ap.add_argument("--out", type=Path, default=Path("data.json"))
    args = ap.parse_args()
    narrate_model = args.narrate_model if args.narrate else None

    if args.set:
        print("building prefab swimmer set:")
        payload = build_set(narrate_model=narrate_model)
        args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote {args.out} — {len(payload['sessions'])} swimmers")
        return

    if args.mock:
        payload = from_mock(
            args.mock.upper(), args.seed, args.baseline, tuple(args.mount),
            n_lengths=args.n_lengths, stroke_period_s=args.stroke_period,
            breathe_every_n_strokes=args.breathe_every,
            mount_slip_deg_per_min=args.mount_slip, noise=not args.clean,
        )
        if narrate_model:
            add_narrative(payload, narrate_model)
    else:
        payload = from_session(args.session)

    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {args.out} — pattern={payload['detected_pattern']} "
          f"mean_d_pitch={payload['summary']['mean_d_pitch_breath']}° "
          f"flags={payload['flags'] or 'none'}")


if __name__ == "__main__":
    main()
