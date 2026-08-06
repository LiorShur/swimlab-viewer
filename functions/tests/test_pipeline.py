"""End-to-end test of the backend processing core, with NO Firebase.

Proves the whole Phase-A loop on synthetic data: a synthetic swimmer ->
Custom-Mode-5 CSV recordings (exactly what a real DOT records) -> the backend
``process_session`` -> the dashboard payloads. Metrics are cross-checked against
the direct ``swimlab`` engine so the CSV round-trip + backend packaging are
faithful.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from swimbackend import pipeline
from swimlab import io, synth


def _csv(df, mode: str = "custom5") -> str:
    """Write a canonical dataframe as a Custom-Mode-5 DOT CSV, return the text."""
    p = Path(tempfile.NamedTemporaryFile(suffix=".csv", delete=False).name)
    io.write_dot_export(df, p, mode=mode)
    text = p.read_text(encoding="utf-8")
    p.unlink(missing_ok=True)
    return text


def _placement_recording(body, placement_id, segment_baseline, mount, seed):
    """A recording dict (trial + T0a/T0b calibration) for one placement."""
    trial, _ = synth.virtual_sensor(body, placement_id, mount_offset_deg=mount, noise=True, seed=seed)
    segs, _ = synth.generate_calibration(mount_offset_deg=mount, pitch_baseline_deg=segment_baseline,
                                         noise=True, seed=seed + 7)
    return {
        "placement_id": placement_id,
        "trial": _csv(trial), "t0a": _csv(segs["t0a"]), "t0b": _csv(segs["t0b"]),
        "swimmer_id": "S-TEST", "mount_offset_deg": list(mount),
    }


@pytest.fixture(scope="module")
def session_recordings():
    body = synth.generate_swim("ROTATOR", seed=42, pitch_baseline_deg=4.0,
                               body_roll_amp_deg=50.0, roll_asymmetry_frac=0.12,
                               arm_asymmetry_frac=0.15)
    pb = body.meta["pelvis_baseline_deg"]
    fb = body.meta["forearm_baseline_deg"]
    return body, [
        _placement_recording(body, "head", 4.0, (3.0, -2.0, 12.0), 42),
        _placement_recording(body, "sacrum", pb, (3.0, -2.0, 12.0), 42),
        _placement_recording(body, "wrist_l", fb, (4.0, -3.0, 11.0), 42),
        _placement_recording(body, "wrist_r", fb, (4.0, -3.0, 11.0), 42),
    ]


def test_process_session_produces_all_placements(session_recordings):
    _body, recs = session_recordings
    out = pipeline.process_session(recs, pool_length_m=25.0)
    assert set(out["placements"]) == {"head", "sacrum", "wrist"}
    for pl in out["placements"].values():
        assert "sessions" in pl and pl["default"] in pl["sessions"]


def test_head_payload_shape_and_metrics(session_recordings):
    _body, recs = session_recordings
    out = pipeline.process_session(recs)
    head = out["placements"]["head"]["sessions"]["S-TEST"]
    assert head["placement"] == "head"
    assert head["detected_pattern"] in ("Lifter", "Rotator")
    assert head["summary"]["mean_d_pitch_breath"] is not None
    assert head["findings"]["en"]["headline"]  # bilingual findings attached
    assert head["findings"]["he"]["headline"]
    assert head["traces"]["t"] and head["traces"]["pitch"] and head["traces"]["roll"]


def test_sacrum_payload_metrics_match_truth(session_recordings):
    body, recs = session_recordings
    out = pipeline.process_session(recs, pool_length_m=25.0)
    s = out["placements"]["sacrum"]["sessions"]["S-TEST"]["summary"]
    assert s["lengths"] == body.truth["n_lengths"]
    assert s["distance_m"] == pytest.approx(body.truth["distance_m"], abs=0.1)
    assert s["stroke_count"] == pytest.approx(body.truth["stroke_count"], abs=3)
    assert s["roll_symmetry_index"] > 0.0  # right-dominant injected


def test_wrist_fusion_recovers_asymmetry(session_recordings):
    _body, recs = session_recordings
    out = pipeline.process_session(recs)
    w = out["placements"]["wrist"]["sessions"]["S-TEST"]
    assert set(w["arms"]) == {"R", "L"}
    assert w["arms"]["R"]["summary"]["pitch_amplitude_deg"] > w["arms"]["L"]["summary"]["pitch_amplitude_deg"]
    assert w["symmetry"]["amplitude_symmetry_index"] > 0.1  # right arm sweeps more


def test_backend_matches_direct_engine_for_head(session_recordings):
    """The CSV round-trip + backend packaging must equal a direct engine run."""
    from swimlab import calibrate, events, metrics
    _body, recs = session_recordings
    head_rec = next(r for r in recs if r["placement_id"] == "head")

    # backend value
    payload = pipeline.process_head(head_rec)
    backend_dpitch = payload["summary"]["mean_d_pitch_breath"]

    # direct engine on the same CSVs
    trial = pipeline._read_csv(head_rec["trial"])
    t0a, t0b = pipeline._read_csv(head_rec["t0a"]), pipeline._read_csv(head_rec["t0b"])
    R = calibrate.fit_transform(t0a, t0b)
    cal = calibrate.apply(trial, R)
    breaths = events.apply_exclusions(events.detect_breath_windows(cal),
                                      events.detect_pushoffs(trial), cal)
    summ = metrics.trial_summary(metrics.per_breath_metrics(cal, breaths))
    direct = round(float(summ["mean_d_pitch_breath"][0]), 2)
    assert backend_dpitch == pytest.approx(direct, abs=1e-6)


def test_single_placement_session(session_recordings):
    """A swim with only one sensor still processes."""
    _body, recs = session_recordings
    sacrum_only = [r for r in recs if r["placement_id"] == "sacrum"]
    out = pipeline.process_session(sacrum_only)
    assert set(out["placements"]) == {"sacrum"}
    assert out["default_placement"] == "sacrum"
