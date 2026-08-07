"""Placement detection is synth-validated: for each placement, the raw-feature
classifier recovers the type, and wrist (far from the torso pair) is confident.
Head-vs-sacrum is correct almost always but with a lower, honest confidence —
that margin is what drives the app's infer-and-confirm UX.
"""

from __future__ import annotations

from swimbackend import placement_detect as pdet
from swimlab import synth

_TRUTH = {"head": "head", "sacrum": "sacrum", "wrist_l": "wrist", "wrist_r": "wrist"}


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


def test_detection_output_shape():
    body = synth.generate_swim("ROTATOR", seed=3, pitch_baseline_deg=4.0, n_lengths=4)
    trial, _ = synth.virtual_sensor(body, "sacrum", mount_offset_deg=(3, -2, 12), noise=True, seed=3)
    r = pdet.infer_placement(trial)
    assert r["placement"] in ("head", "sacrum", "wrist")
    assert 0.0 <= r["confidence"] <= 1.0
    assert set(r["scores"]) == {"head", "sacrum", "wrist"}
    assert "pitch_amp_deg" in r["features"]
