"""Infer sensor placement (head / sacrum / wrist) from a raw DOT recording.

Calibration-INDEPENDENT: it reads only gravity-referenced tilt (from the
quaternion), gyro energy, and the pitch-event rate — so it runs on the raw file
before any T0 transform. Used for *infer-and-confirm*: the app pre-fills the
placement guess with a confidence, the user confirms/overrides. It never routes
silently.

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
from scipy.signal import find_peaks
from scipy.spatial.transform import Rotation

# Feature order: [pitch_amp°, roll/pitch ratio, pitch-peak rate /s, gyro RMS °/s]
_FEATURES = ("pitch_amp_deg", "roll_pitch_ratio", "pitch_peak_rate_hz", "gyro_rms_dps")
_CENTROIDS = {
    "head":   np.array([32.2, 3.03, 0.22, 94.6]),
    "sacrum": np.array([22.8, 4.35, 0.32, 106.1]),
    "wrist":  np.array([109.8, 0.31, 0.32, 123.8]),
}
# Per-feature scale (pooled within-class SD; pitch-peak-rate floored so a
# possibly-noisy real-world feature isn't over-weighted).
_SCALE = np.array([5.0, 0.6, 0.06, 4.0])


def extract_features(df) -> dict:
    """Calibration-free features from a canonical DOT dataframe."""
    t = df["t"].to_numpy()
    dur = float(t[-1] - t[0]) or 1.0
    fs = 1.0 / float(np.median(np.diff(t)))

    quat = np.column_stack([df["quat_x"], df["quat_y"], df["quat_z"], df["quat_w"]])  # xyzw
    g = Rotation.from_quat(quat).inv().apply(np.tile([0.0, 0.0, 1.0], (len(df), 1)))  # gravity in sensor frame
    pitch = np.degrees(np.arctan2(g[:, 0], g[:, 2]))
    roll = np.degrees(np.arctan2(g[:, 1], g[:, 2]))
    amp = lambda x: float(np.percentile(x, 95) - np.percentile(x, 5))
    pa, ra = amp(pitch), amp(roll)

    gyr = np.column_stack([df["gyr_x"], df["gyr_y"], df["gyr_z"]])
    gyr_rms = float(np.sqrt(np.mean(np.sum(gyr ** 2, axis=1))))

    peaks, _ = find_peaks(pitch - np.median(pitch), prominence=8, distance=int(max(1, 1.5 * fs)))
    return {
        "pitch_amp_deg": round(pa, 2),
        "roll_pitch_ratio": round(ra / max(pa, 1.0), 3),
        "pitch_peak_rate_hz": round(len(peaks) / dur, 4),
        "gyro_rms_dps": round(gyr_rms, 2),
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
