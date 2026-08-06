"""Optional LLM narration layer for the viewer, **placement-aware**.

The analysis pipeline (calibrate → events → metrics → stats) stays fully
deterministic — Claude is **never** in the measurement loop. This module runs
*after* the numbers exist and only rewrites the *interpretation* layer, for any
sensor placement (head / sacrum / wrist). It mirrors the rule-based
``findings.py`` in structure, but produces richer prose.

Grounding discipline (a pre-validation research prototype):

* Claude is handed a **fixed fact table** of already-computed metrics for ONE
  placement and told to interpret only those — never invent or recompute.
* Structured output (a JSON schema) forces every correction to cite the metric
  it rests on, so a claim can't float free of the data.
* The system prompt bakes in the hedging: illustrative, hypothesis-based, not a
  validated clinical finding.

The Cloudflare Worker (``worker/narrate-worker.js``) is a straight port of this
module — keep the base prompt, per-placement guides, fact tables and schema in
sync so live and baked narratives read the same.

If ``anthropic`` isn't installed or ``ANTHROPIC_API_KEY`` isn't set, the caller
catches the error and falls back to the rule-based ``findings`` — nothing breaks.
"""

from __future__ import annotations

import json

# The head module's canonical drill vocabulary (mirrors DRILL in template.html).
# Only the head placement offers drills; the other placements give plain actions.
DRILL_MENU = [
    "Single-arm freestyle",
    "6-kick / 3-stroke switch",
    "“One goggle out” cue",
    "Exhale-pattern breathing",
    "Bilateral breathing (every 3)",
    "Tempo-trainer breathing",
    "Side-kick balance (kick on your side)",
    "Steady-state sets with a low-head cue",
]

# --------------------------------------------------------------------------- #
# Prompts: one shared base + a per-placement guide
# --------------------------------------------------------------------------- #

_BASE_SYSTEM = """You write the interpretation section of a swim-technique \
analysis prototype that reads body-worn IMUs (Movella/Xsens DOT). You are given \
a table of metrics that have ALREADY been computed by a deterministic pipeline \
for ONE sensor placement. Your job is to interpret those numbers — not to \
measure anything.

Hard rules:
- This is a research prototype whose findings have NOT been validated on real \
swimmers. Everything you write is illustrative and hypothesis-based. Never state \
a finding as proven. Use language like "suggests", "consistent with", "points \
toward" — never "you have" or "this proves".
- Interpret ONLY the metrics in the table. Never invent, estimate, or recompute a \
number. Every correction you give must cite the specific metric and value it rests \
on, in its "metric" field.
- Reason across the WHOLE metric vector for this placement to say something more \
specific than any single number would.
- Be concise and readable. Coach-facing, plain sentences, no hype.

You write TWO layers from the same numbers:

1. A COACH layer (detailed): a one-paragraph summary and 3–6 correction points \
(each with its grounding metric).{drills_clause}

2. A SWIMMER layer (plain): for the recreational swimmer themselves, not a coach.
- headline: ONE short sentence, ~10 words max, NO metric names and NO numbers, \
saying in plain terms what their technique does.
- swimmer_summary: 2 short sentences, warm and encouraging, explaining what it \
means and why it matters — still no jargon, no numbers, no degrees.
- swimmer_actions: 2–3 very short, concrete things to try, in plain language a \
swimmer can act on in the water (no metric talk).

Keep the two layers consistent with each other and with the metrics.

Placement context:
{guide}"""

_DRILLS_CLAUSE = (
    " Then 3–5 drills (each with a swimmer-specific reason), chosen ONLY from the "
    "menu given in the fact table; keep the names recognisable and tailor the "
    '"why" to this swimmer.'
)

_GUIDE = {
    "head": (
        "This sensor is on the HEAD (skull). It measures breath technique: whether "
        "the swimmer lifts the head (Δpitch) or rotates to breathe (roll). The "
        "lifter/rotator gate is mean Δpitch vs the gate value; lifting the head "
        "drops the hips and adds drag, while rotating to breathe is the efficient "
        "pattern the study favours. The asymmetry index relates to the breathing "
        "side; the pitch SD is breath-to-breath consistency; pitch drift is fatigue "
        "across the swim."
    ),
    "sacrum": (
        "This sensor is on the SACRUM (pelvis). It measures whole-body roll and the "
        "wall push-offs: lengths, distance, stroke count, tempo/stroke rate, "
        "body-roll amplitude, LEFT/RIGHT roll symmetry, push-off count/interval and "
        "pace drift. Efficient freestyle has ample, symmetric body roll and steady "
        "pace; a clear L/R roll asymmetry, very little (or excessive) roll, or a "
        "pace that fades across lengths is worth flagging. Distance is lengths × "
        "pool length — an IMU cannot measure position."
    ),
    "wrist": (
        "This sensor is on the WRIST (forearm) — one per arm. It measures each arm's "
        "stroke phases from forearm pitch: stroke count/rate, pull duration and the "
        "pull fraction of the cycle, and pitch amplitude (the arc the hand sweeps "
        "from the over-water recovery down to the catch). The FUSION of the two "
        "arms gives left/right symmetry (amplitude, stroke count, pull duration) and "
        "the phase offset (≈0.5 cycles = clean antiphase, one hand entering as the "
        "other finishes the pull). Flag a dominant arm, uneven stroke counts, or "
        "timing that drifts off antiphase."
    ),
}

# Language addendum for the OFFLINE single-language path (baking with --lang he).
# The live Worker instead asks for both languages in one call (translation).
_LANG_INSTRUCTION = {
    "he": (
        "\n\nWrite ALL prose you produce in natural Hebrew — both layers. Address "
        "the swimmer in the masculine singular (Hebrew גוף שני, זכר יחיד) "
        "consistently and never switch to feminine forms. Keep the grounding "
        '"metric" strings and all numbers, units and symbols exactly as in the '
        "fact table. If drills are present, pick from the English menu but "
        "translate the chosen name into Hebrew."
    ),
}


def _correction_schema() -> dict:
    return {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"point": {"type": "string"}, "metric": {"type": "string"}},
            "required": ["point", "metric"],
        },
    }


def schema_for(placement: str) -> dict:
    """The output schema for a placement — drills only for the head."""
    props = {
        "headline": {"type": "string"},
        "swimmer_summary": {"type": "string"},
        "swimmer_actions": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
        "corrections": _correction_schema(),
    }
    required = ["headline", "swimmer_summary", "swimmer_actions", "summary", "corrections"]
    if placement == "head":
        props["drills"] = {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"name": {"type": "string"}, "why": {"type": "string"}},
                "required": ["name", "why"],
            },
        }
        required.append("drills")
    return {"type": "object", "additionalProperties": False, "properties": props,
            "required": required}


def detect_placement(payload: dict) -> str:
    """Infer the placement from a payload's shape."""
    if payload.get("placement") in ("head", "sacrum", "wrist"):
        return payload["placement"]
    if "arms" in payload:
        return "wrist"
    s = payload.get("summary", {})
    if "body_roll_amplitude_deg" in s:
        return "sacrum"
    if "mean_d_pitch_breath" in s:
        return "head"
    return "head"


def system_prompt(placement: str) -> str:
    """The full system prompt for a placement (base + drills clause + guide)."""
    return _BASE_SYSTEM.format(
        drills_clause=_DRILLS_CLAUSE if placement == "head" else "",
        guide=_GUIDE.get(placement, _GUIDE["head"]),
    )


# --------------------------------------------------------------------------- #
# Fact tables (one per placement)
# --------------------------------------------------------------------------- #


def _head_facts(payload: dict) -> str:
    s = payload["summary"]
    valid = [b for b in payload.get("breaths", []) if not b.get("excluded")]
    lines = [
        f"Session: {payload.get('session', '')}",
        "Placement: HEAD (skull)",
        f"Detected pattern (pipeline): {payload.get('detected_pattern')} "
        f"(lifter/rotator gate = {payload.get('gate_threshold_deg')}° mean Δpitch)",
    ]
    if payload.get("archetype"):
        lines.append(f"Synthetic ground-truth archetype: {payload['archetype']} "
                     "(context only — the pipeline never saw this label)")
    lines += [
        "",
        "Trial metrics (already computed — do not recompute):",
        f"  mean Δpitch on the breath : {s['mean_d_pitch_breath']}°   (gate {payload.get('gate_threshold_deg')}°)",
        f"  mean peak roll on the breath: {s['mean_peak_roll_breath']}°",
        f"  roll:pitch ratio           : {s.get('mean_roll_pitch_ratio')}  (dimensionless, secondary)",
        f"  breath-to-breath pitch SD  : {s['pitch_variability']}°",
        f"  asymmetry index            : {s['asymmetry_index']}  ((left − right) / mean Δpitch; +ve = left breath bigger)",
        f"  valid breaths              : {s['n_valid']} of {s['n_breaths']} ({s['n_excluded']} excluded by protocol)",
        f"  quality flags              : {', '.join(payload.get('flags', [])) or 'none'}",
    ]
    if valid:
        lines.append("")
        lines.append("Per valid breath (t_start s, side, Δpitch°, peak_roll°):")
        for b in valid:
            lines.append(f"  t={b.get('t_start')}  {b.get('side')}  "
                         f"Δpitch={b.get('d_pitch_breath')}  roll={b.get('peak_roll_breath')}")
    lines += ["", f"Drill menu (choose from these names only): {', '.join(DRILL_MENU)}"]
    return "\n".join(lines)


def _sacrum_facts(payload: dict) -> str:
    s = payload["summary"]
    lines = [
        f"Session: {payload.get('session', '')}",
        "Placement: SACRUM (pelvis)",
    ]
    if payload.get("archetype"):
        lines.append(f"Synthetic ground-truth archetype: {payload['archetype']} (context only)")
    lines += [
        "",
        "Trial metrics (already computed — do not recompute):",
        f"  lengths                    : {s.get('lengths')}",
        f"  distance                   : {s.get('distance_m')} m  (= lengths × pool length; no position from an IMU)",
        f"  stroke count               : {s.get('stroke_count')} ({s.get('n_valid_strokes')} valid)",
        f"  tempo                      : {s.get('tempo_spm')} strokes/min",
        f"  stroke rate                : {s.get('stroke_rate_cpm')} cycles/min",
        f"  body-roll amplitude        : {s.get('body_roll_amplitude_deg')}°",
        f"  mean peak roll right/left  : {s.get('mean_peak_roll_right_deg')}° / {s.get('mean_peak_roll_left_deg')}°",
        f"  roll symmetry index        : {s.get('roll_symmetry_index')}  ((right − left)/mean; +ve = rolls further right)",
        f"  push-offs                  : {s.get('pushoff_count')} (mean interval {s.get('mean_pushoff_interval_s')} s)",
        f"  pace drift                 : {s.get('pace_drift_s_per_length')} s/length  (+ve = slowing across the swim)",
        f"  quality flags              : {', '.join(payload.get('flags', [])) or 'none'}",
    ]
    return "\n".join(lines)


def _wrist_facts(payload: dict) -> str:
    R = payload["arms"]["R"]["summary"]
    L = payload["arms"]["L"]["summary"]
    sy = payload.get("symmetry", {})
    lines = [
        f"Session: {payload.get('session', '')}",
        "Placement: WRIST (forearm, left + right)",
    ]
    if payload.get("archetype"):
        lines.append(f"Synthetic ground-truth archetype: {payload['archetype']} (context only)")
    lines += [
        "",
        "Per-arm metrics (already computed — do not recompute):",
        f"  RIGHT: strokes {R.get('stroke_count')} ({R.get('n_valid_strokes')} valid), "
        f"rate {R.get('stroke_rate_cpm')} cyc/min, pitch amplitude {R.get('pitch_amplitude_deg')}°, "
        f"mean pull {R.get('mean_pull_duration_s')} s, pull fraction {R.get('pull_fraction')} of the cycle",
        f"  LEFT : strokes {L.get('stroke_count')} ({L.get('n_valid_strokes')} valid), "
        f"rate {L.get('stroke_rate_cpm')} cyc/min, pitch amplitude {L.get('pitch_amplitude_deg')}°, "
        f"mean pull {L.get('mean_pull_duration_s')} s, pull fraction {L.get('pull_fraction')} of the cycle",
        "",
        "Left/right symmetry (fusion; each index = (R − L)/mean, 0 = symmetric):",
        f"  amplitude symmetry index   : {sy.get('amplitude_symmetry_index')}",
        f"  stroke-count symmetry index: {sy.get('stroke_count_symmetry_index')}",
        f"  pull-duration symmetry idx : {sy.get('pull_duration_symmetry_index')}",
        f"  phase offset               : {sy.get('mean_phase_offset_cycles')} cycles  (0.5 = clean antiphase)",
        f"  quality flags              : {', '.join(payload.get('flags', [])) or 'none'}",
    ]
    return "\n".join(lines)


_FACTS = {"head": _head_facts, "sacrum": _sacrum_facts, "wrist": _wrist_facts}


def fact_table(payload: dict, placement: str | None = None) -> str:
    """Render a payload's metrics as a compact fact table for its placement."""
    placement = placement or detect_placement(payload)
    return _FACTS[placement](payload)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def narrate_payload(payload: dict, *, placement: str | None = None,
                    model: str = "claude-opus-5", api_key: str | None = None,
                    effort: str = "low", lang: str = "en") -> dict:
    """Call Claude to produce a grounded interpretation for one placement payload.

    Auto-detects the placement (head / sacrum / wrist) from the payload unless
    given. Returns a dict ``{headline, swimmer_summary, swimmer_actions, summary,
    corrections[, drills], model, lang, placement}`` ready to attach as
    ``payload["narrative"]``. ``lang`` selects the output language ("en"/"he") —
    only prose changes; metric citations stay as computed. Raises on any failure
    so the caller can fall back to the rule-based findings.
    """
    try:
        import anthropic
    except ImportError as e:  # pragma: no cover - environment dependent
        raise RuntimeError("The 'anthropic' package is not installed. Run: pip install anthropic") from e

    placement = placement or detect_placement(payload)
    client = anthropic.Anthropic(api_key=api_key)  # reads ANTHROPIC_API_KEY if None

    output_config = {"format": {"type": "json_schema", "schema": schema_for(placement)}}
    if "haiku" not in model.lower():  # Haiku 4.5 rejects output_config.effort
        output_config["effort"] = effort

    kwargs = dict(
        model=model,
        max_tokens=2000,
        system=system_prompt(placement) + _LANG_INSTRUCTION.get(lang, ""),
        output_config=output_config,
        messages=[{"role": "user", "content": fact_table(payload, placement)}],
    )
    if "haiku" not in model.lower():
        kwargs["thinking"] = {"type": "adaptive"}

    resp = client.messages.create(**kwargs)
    if resp.stop_reason == "refusal":
        raise RuntimeError(
            f"Model declined to answer ({getattr(resp.stop_details, 'category', None)}); "
            "keeping the rule-based text.")

    text = next((b.text for b in resp.content if b.type == "text"), None)
    if not text:
        raise RuntimeError("No text block in the response.")
    data = json.loads(text)  # schema-constrained, so this parses
    data["model"] = resp.model
    data["lang"] = lang
    data["placement"] = placement
    return data
