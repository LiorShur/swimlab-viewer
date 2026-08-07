"""Placement detection is synth-validated: for each placement, the raw-feature
classifier recovers the type, and wrist (far from the torso pair) is confident.
Head-vs-sacrum is correct almost always but with a lower, honest confidence —
that margin is what drives the app's infer-and-confirm UX.
"""

from __future__ import annotations

import numpy as np
import polars as pl
from scipy.spatial.transform import Rotation

from swimbackend import placement_detect as pdet
from swimlab import synth

_TRUTH = {"head": "head", "sacrum": "sacrum", "wrist_l": "wrist", "wrist_r": "wrist"}


def _rotate_mount(df, euler_deg):
    """Apply a constant extra sensor rotation — simulates a different mount
    orientation. Detection must be invariant to this."""
    q = np.column_stack([df["quat_x"], df["quat_y"], df["quat_z"], df["quat_w"]])
    qq = (Rotation.from_quat(q) * Rotation.from_euler("xyz", euler_deg, degrees=True)).as_quat()
    return df.with_columns(quat_x=pl.Series(qq[:, 0]), quat_y=pl.Series(qq[:, 1]),
                           quat_z=pl.Series(qq[:, 2]), quat_w=pl.Series(qq[:, 3]))


def test_detection_recovers_placement_type():
    correct = total = 0
    wrist_conf = []
    for arch in ("LIFTER", "ROTATOR", "MIXED"):
        for seed in (2, 9, 15):
            body = synth.generate_swim(arch, seed=seed, pitch_baseline_deg=4.0,
                                       body_roll_amp_deg=50.0, n_lengths=4)
            for pl, exp in _TRUTH.items():
                trial, _ = synth.virtual_sensor(body, pl, mount_offset_deg=(4, -3, 11),
                                                noise=True, seed=seed)
                r = pdet.infer_placement(trial)
                total += 1
                correct += r["placement"] == exp
                if exp == "wrist":
                    wrist_conf.append(r["confidence"])

    assert correct / total >= 0.9          # ≥90% type accuracy across archetypes/seeds
    assert min(wrist_conf) > 0.9           # wrist is unambiguous


def test_detection_is_mount_orientation_invariant():
    """A constant mount rotation must not change the placement type — this is the
    regression for 'head file detected as wrist' (an axis-dependent feature bug)."""
    body = synth.generate_swim("ROTATOR", seed=4, pitch_baseline_deg=4.0,
                               body_roll_amp_deg=50.0, n_lengths=4)
    for pl_id, exp in (("head", "head"), ("sacrum", "sacrum"), ("wrist_l", "wrist")):
        trial, _ = synth.virtual_sensor(body, pl_id, mount_offset_deg=(3, -2, 12), noise=True, seed=4)
        for euler in [(0, 0, 0), (0, 0, 60), (70, 0, 0), (0, 85, 0), (-50, 30, 40)]:
            got = pdet.infer_placement(_rotate_mount(trial, euler))["placement"]
            assert got == exp, f"{pl_id} under mount {euler} -> {got}"
            # crucially, a torso sensor is NEVER mislabelled wrist under any mount
            if exp != "wrist":
                assert got != "wrist"


def test_detection_output_shape():
    body = synth.generate_swim("ROTATOR", seed=3, pitch_baseline_deg=4.0, n_lengths=4)
    trial, _ = synth.virtual_sensor(body, "sacrum", mount_offset_deg=(3, -2, 12), noise=True, seed=3)
    r = pdet.infer_placement(trial)
    assert r["placement"] in ("head", "sacrum", "wrist")
    assert 0.0 <= r["confidence"] <= 1.0
    assert set(r["scores"]) == {"head", "sacrum", "wrist"}
    assert "gyro_rms_dps" in r["features"]
