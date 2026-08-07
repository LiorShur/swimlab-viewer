"""Infer sensor placement (head / sacrum / wrist) from a raw DOT recording.

Calibration-INDEPENDENT **and mount-orientation-invariant**: it reads only the
angular travel of the gravity direction and gyro (angular-speed) magnitude — so
it runs on the raw file before any T0 transform and is unaffected by how the
sensor happens to be rotated on the body. Used for *infer-and-confirm*: the app
pre-fills the placement guess with a confidence, the user confirms/overrides. It
never routes silently.

Not attempted here: left vs right (ambiguous from one sensor) — the caller
confirms the side. Ankle / upper-arm are out of scope until the engine has
modules + synth for them.

Centroids/scales are tuned on ``synth`` (3 archetypes × 6 seeds × 3 mounts,
n=54/placement) and validated in ``tests``. Like ``io.py`` and the single-file
calibration window, they are ``# TODO(real-file)`` — reconfirm on real
recordings before trusting the head-vs-sacrum split.
"""

from __future__ import annotations

import numpy as np
from scipy.spatial.transform import Rotation

# Features must be invariant to the sensor's *mounting orientation* — we run
# before calibration, so anything that depends on which sensor axis points where
# (e.g. per-axis pitch vs roll amplitude) is unusable: a constant mount rotation
# would swing it wildly and mislabel the placement. These three are invariant:
#   grav_span_deg  — angular travel of the gravity direction (how much the sensor
#                    tilts overall, regardless of axis)
#   gyro_rms_dps   — RMS angular speed (|ω| is frame-independent)
#   gyro_p95_dps   — peak angular speed (the wrist's fast arm rotation stands out)
_FEATURES = ("grav_span_deg", "gyro_rms_dps", "gyro_p95_dps")
_CENTROIDS = {
    "head":   np.array([55.8, 94.6, 123.0]),
    "sacrum": np.array([49.7, 106.1, 122.5]),
    "wrist":  np.array([63.0, 123.8, 187.1]),
}
# Per-feature scale (pooled within-class SD).
_SCALE = np.array([7.0, 3.6, 9.5])


def extract_features(df) -> dict:
    """Mount-invariant, calibration-free features from a canonical DOT dataframe."""
    quat = np.column_stack([df["quat_x"], df["quat_y"], df["quat_z"], df["quat_w"]])  # xyzw
    g = Rotation.from_quat(quat).inv().apply(np.tile([0.0, 0.0, 1.0], (len(df), 1)))  # gravity in sensor frame
    gm = g.mean(axis=0)
    gm = gm / (np.linalg.norm(gm) or 1.0)
    # angle of each gravity sample from the mean gravity direction — invariant to
    # a constant rotation of the whole trajectory (rotating the sphere preserves
    # angles between points).
    grav_span = float(np.percentile(np.degrees(np.arccos(np.clip(g @ gm, -1.0, 1.0))), 95))

    gyr = np.linalg.norm(np.column_stack([df["gyr_x"], df["gyr_y"], df["gyr_z"]]), axis=1)
    return {
        "grav_span_deg": round(grav_span, 2),
        "gyro_rms_dps": round(float(np.sqrt(np.mean(gyr ** 2))), 2),
        "gyro_p95_dps": round(float(np.percentile(gyr, 95)), 2),
    }


def infer_placement(df) -> dict:
    """``{placement, confidence, scores, features}``.

    Nearest scaled-centroid over the four features; confidence is the separation
    margin (``1 - d_best/d_second``), so wrist (far from the torso pair) scores
    near 1 and a close head/sacrum call scores lower.
    """
    feats = extract_features(df)
    x = np.array([feats[k] for k in _FEATURES])
    dists = {pl: float(np.sqrt(np.sum(((x - c) / _SCALE) ** 2))) for pl, c in _CENTROIDS.items()}
    order = sorted(dists, key=dists.get)
    best, second = order[0], order[1]
    conf = max(0.0, min(1.0, 1.0 - dists[best] / dists[second])) if dists[second] > 0 else 1.0
    return {
        "placement": best,
        "confidence": round(conf, 3),
        "scores": {pl: round(d, 2) for pl, d in dists.items()},
        "features": feats,
    }
