"""Write a full canonical-schema session directory in one command.

A "session" is the on-disk contract ``swimlab.pipeline.run_session`` reads: the
two static calibration poses plus the trial, each a canonical-schema parquet
file. This helper synthesises a matching set (one swimmer = one prone baseline
and mount, shared by calibration and trial) so you can exercise the whole
pipeline against real files -- and it is the template a real Movella DOT export
will follow once ``swimlab/io.py`` is written.

    python src/make_session.py --mock LIFTER --seed 42 --out sessions/s01
    python -c "from swimlab.pipeline import run_session; \
               t,f = run_session('sessions/s01'); print(t.head()); print(f)"

Files written (names come from ``swimlab.pipeline.SESSION_FILES``):

    <out>/t0a.parquet      upright, gaze-horizontal calibration pose
    <out>/t0b.parquet      face-down prone pose (the zero reference)
    <out>/t0c.parquet      three sync-marker nods (optional for run_session)
    <out>/trial.parquet    the swim (T7: 4 x 25 m front crawl, breathing every 3)
    <out>/ground_truth.json  the injected truth (metadata; ignored by run_session)

The parquet files carry the canonical dataframe schema only -- ``t``, ``quat_*``,
``acc_*``, ``gyr_*``, ``mag_*`` -- exactly what a real export must be normalised
to. Nothing swimlab-synthetic leaks into them beyond that schema.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def make_session(
    out_dir: Path,
    archetype: str,
    *,
    seed: int = 100,
    baseline: float = 5.0,
    mount: tuple[float, float, float] = (4.0, -3.0, 11.0),
    n_lengths: int = 4,
    noise: bool = True,
) -> Path:
    """Synthesise and write a matching calibration + trial session directory."""
    from swimlab import synth
    from swimlab.pipeline import SESSION_FILES

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Calibration and trial MUST share one prone baseline and mount (one swimmer,
    # one prone pose) -- the ground truth is gravity-referenced relative to T0b.
    segs, _calib_gt = synth.generate_calibration(
        mount_offset_deg=mount, pitch_baseline_deg=baseline, noise=noise, seed=seed + 7
    )
    trial, gt = synth.generate_trial(
        archetype, n_lengths=n_lengths, mount_offset_deg=mount,
        noise=noise, seed=seed, pitch_baseline_deg=baseline,
    )

    segs["t0a"].write_parquet(out_dir / SESSION_FILES["t0a"])
    segs["t0b"].write_parquet(out_dir / SESSION_FILES["t0b"])
    segs["t0c"].write_parquet(out_dir / SESSION_FILES["t0c"])
    trial.write_parquet(out_dir / SESSION_FILES["trial"])
    (out_dir / "ground_truth.json").write_text(json.dumps(gt, indent=2), encoding="utf-8")

    n_valid = gt["summary"]["n_valid_breaths"]
    print(
        f"wrote session -> {out_dir}/  ({archetype}, seed={seed}, "
        f"baseline={baseline}°, mount={mount})\n"
        f"  {n_valid}/{gt['summary']['n_breaths']} valid breaths, "
        f"true mean d_pitch = {gt['summary']['true_mean_d_pitch_deg']}°\n"
        f"  run it:  python -c \"from swimlab.pipeline import run_session; "
        f"t,f=run_session('{out_dir}'); print(t.select(['t_start','side',"
        f"'d_pitch_breath']).head()); print('flags:', f)\""
    )
    return out_dir


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mock", default="LIFTER", metavar="ARCHETYPE",
                    help="LIFTER|ROTATOR|MIXED|FLAT|ASYMMETRIC (default LIFTER)")
    ap.add_argument("--seed", type=int, default=100)
    ap.add_argument("--baseline", type=float, default=5.0, help="prone head pitch, deg")
    ap.add_argument("--mount", type=float, nargs=3, default=(4.0, -3.0, 11.0),
                    metavar=("X", "Y", "Z"), help="sensor mount offset, deg")
    ap.add_argument("--n-lengths", type=int, default=4)
    ap.add_argument("--clean", action="store_true", help="no sensor noise (round-trip test)")
    ap.add_argument("--out", type=Path, required=True, help="session directory to write")
    args = ap.parse_args()

    make_session(
        args.out, args.mock.upper(), seed=args.seed, baseline=args.baseline,
        mount=tuple(args.mount), n_lengths=args.n_lengths, noise=not args.clean,
    )


if __name__ == "__main__":
    main()
