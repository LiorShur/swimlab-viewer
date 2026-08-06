"""Generate sample Custom-Mode-5 DOT recordings for testing the backend.

Writes, for a synthetic swimmer, a Custom-Mode-5 CSV (raw Acc + Quaternion +
Angular velocity — exactly what a real DOT records) for each placement's trial
and its T0a/T0b calibration poses, plus a ``request.json`` ready to POST at the
``process_session`` Cloud Function (emulator or live).

Usage:
    python tools/make_sample_recordings.py --out /tmp/swim_sample [--n-lengths 2]

Then, e.g. against the emulator:
    curl -X POST \
      http://localhost:5001/<PROJECT>/us-central1/process_session \
      -H "Content-Type: application/json" -d @/tmp/swim_sample/request.json
    # -> {"result": {"placements": {...}, "default_placement": "sacrum"}}
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from swimlab import io, synth

# (placement_id, segment_baseline_key, mount) — the four sensors of a full swim.
_PLACEMENTS = [
    ("head", "pitch_baseline_deg", (3.0, -2.0, 12.0)),
    ("sacrum", "pelvis_baseline_deg", (3.0, -2.0, 12.0)),
    ("wrist_l", "forearm_baseline_deg", (4.0, -3.0, 11.0)),
    ("wrist_r", "forearm_baseline_deg", (4.0, -3.0, 11.0)),
]


def _write_csv(df, path: Path) -> str:
    io.write_dot_export(df, path, mode="custom5")
    return path.read_text(encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True, help="output directory")
    ap.add_argument("--archetype", default="ROTATOR")
    ap.add_argument("--n-lengths", type=int, default=2, help="lengths (small = smaller files)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--pool-length-m", type=float, default=25.0)
    ap.add_argument("--swimmer-id", default="S-SAMPLE")
    args = ap.parse_args()

    if not hasattr(io, "write_dot_export"):
        raise SystemExit(
            "Your installed swimlab is too old: it has no io.write_dot_export.\n"
            "Update the engine to the branch with the multi-placement modules:\n"
            "    cd /path/to/swimlab && git checkout claude/synth-head-imu-generator-3tljlr\n"
            "    git pull && pip install -e .\n"
            f"(importing swimlab from: {getattr(io, '__file__', '?')})"
        )

    args.out.mkdir(parents=True, exist_ok=True)

    body = synth.generate_swim(
        args.archetype, seed=args.seed, pitch_baseline_deg=4.0, n_lengths=args.n_lengths,
        body_roll_amp_deg=50.0, roll_asymmetry_frac=0.12, arm_asymmetry_frac=0.15,
        pool_length_m=args.pool_length_m,
    )

    recordings = []
    for placement_id, baseline_key, mount in _PLACEMENTS:
        baseline = body.meta[baseline_key]
        trial, _ = synth.virtual_sensor(body, placement_id, mount_offset_deg=mount, noise=True, seed=args.seed)
        segs, _ = synth.generate_calibration(mount_offset_deg=mount, pitch_baseline_deg=baseline,
                                             noise=True, seed=args.seed + 7)
        d = args.out / placement_id
        d.mkdir(exist_ok=True)
        rec = {
            "placement_id": placement_id,
            "trial": _write_csv(trial, d / "trial.csv"),
            "t0a": _write_csv(segs["t0a"], d / "t0a.csv"),
            "t0b": _write_csv(segs["t0b"], d / "t0b.csv"),
            "swimmer_id": args.swimmer_id,
            "mount_offset_deg": list(mount),
        }
        recordings.append(rec)

    request = {"data": {"recordings": recordings, "pool_length_m": args.pool_length_m}}
    req_path = args.out / "request.json"
    req_path.write_text(json.dumps(request), encoding="utf-8")

    total_kb = sum(len(r["trial"]) + len(r["t0a"]) + len(r["t0b"]) for r in recordings) // 1024
    print(f"wrote {len(recordings)} placements to {args.out}")
    print(f"  CSVs per placement: trial.csv, t0a.csv, t0b.csv")
    print(f"  POST body: {req_path}  (~{total_kb} KB inline)")
    print("  placements:", ", ".join(r["placement_id"] for r in recordings))


if __name__ == "__main__":
    main()
