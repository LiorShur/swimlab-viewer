"""Optional LLM narration layer for the viewer (``export_session.py --narrate``).

The analysis pipeline (calibrate → events → metrics → stats) stays fully
deterministic — Claude is **never** in the measurement loop. This module runs
*after* the numbers exist and only rewrites the *interpretation* layer that the
viewer otherwise generates with hardcoded rules (``summaryText`` /
``buildFindings`` in ``template.html``).

Grounding discipline (this is a pre-validation research prototype):

* Claude is handed a **fixed fact table** of already-computed metrics and told to
  interpret only those — never to invent or recompute a number.
* Structured output (a JSON schema) forces every correction to cite the metric
  it rests on, so a claim can't float free of the data.
* The system prompt bakes in the hedging: everything here is illustrative and
  hypothesis-based, not a validated clinical finding.

If ``anthropic`` isn't installed or ``ANTHROPIC_API_KEY`` isn't set, the caller
catches the error and falls back to the rule-based text — nothing breaks.
"""

from __future__ import annotations

import json

# The app's canonical drill vocabulary (mirrors DRILL in template.html). Claude
# selects from this menu so drill names stay consistent with the rest of the UI;
# it writes the swimmer-specific rationale itself.
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

_SYSTEM = """You write the interpretation section of a swim-technique analysis \
prototype that reads a head-mounted IMU. You are given a table of metrics that \
have ALREADY been computed by a deterministic pipeline. Your job is to interpret \
those numbers for a coach — not to measure anything.

Hard rules:
- This is a research prototype whose core hypothesis (that head pitch is a real \
diagnostic gate) has NOT been validated. Everything you write is illustrative and \
hypothesis-based. Never state a finding as proven. Use language like "suggests", \
"consistent with", "points toward" — never "you have" or "this proves".
- Interpret ONLY the metrics in the table. Never invent, estimate, or recompute a \
number. Every correction you give must cite the specific metric and value it rests \
on, in its "metric" field (e.g. "mean Δpitch 28.8° vs 13.5° gate").
- Reason across the whole metric vector — combine pitch, roll, asymmetry, \
variability, drift, breathing side and the per-breath list — to say something more \
specific than any single number would (e.g. how asymmetry relates to the breathing \
side, or whether a pattern drifts with fatigue across the swim).
- Choose drills only from the provided menu. Keep the names recognisable; write a \
"why" tailored to THIS swimmer's numbers.
- Be concise and readable. Coach-facing, plain sentences, no hype.

You write TWO layers from the same numbers:

1. A COACH layer (detailed): a one-paragraph summary, 3–6 correction points \
(each with its grounding metric), and 3–5 drills (each with a swimmer-specific \
reason). This is the technical read described above.

2. A SWIMMER layer (plain): for the recreational swimmer themselves, not a coach.
- headline: ONE short sentence, ~10 words max, NO metric names and NO numbers, \
saying in plain terms what their breathing does (e.g. "You lift your head to \
breathe" or "Your breathing looks efficient").
- swimmer_summary: 2 short sentences, warm and encouraging, explaining what it \
means and why it matters — still no jargon, no numbers, no degrees.
- swimmer_actions: 2–3 very short, concrete things to try, in plain language a \
swimmer can act on in the water (no metric talk).

Keep the two layers consistent with each other and with the metrics."""

# Language addendum — only the prose Claude writes changes language; the fact
# table, metric names, numbers and units stay as given. Mirror in the Worker
# (worker/narrate-worker.js LANG_INSTRUCTION).
_LANG_INSTRUCTION = {
    "he": (
        "\n\nWrite ALL prose you produce in natural Hebrew — both layers: the "
        "headline, swimmer_summary and swimmer_actions (plain, warm, everyday "
        'Hebrew for a swimmer), and the coach summary, every correction "point", '
        'and every drill "name" and "why". Keep the grounding "metric" strings '
        "and all numbers, units and symbols (e.g. Δpitch, °, the gate value) "
        "exactly as in the fact table. Pick drills from the English menu but "
        "translate the chosen name into Hebrew."
    ),
}

_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "headline": {"type": "string"},
        "swimmer_summary": {"type": "string"},
        "swimmer_actions": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
        "corrections": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "point": {"type": "string"},
                    "metric": {"type": "string"},
                },
                "required": ["point", "metric"],
            },
        },
        "drills": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["name", "why"],
            },
        },
    },
    "required": ["headline", "swimmer_summary", "swimmer_actions",
                 "summary", "corrections", "drills"],
}


def _fact_table(payload: dict) -> str:
    """Render the payload's metrics as a compact, unambiguous fact table for the
    model. Only derived metrics go in — never raw traces or anything the model
    could mistake for something to recompute."""
    s = payload["summary"]
    valid = [b for b in payload.get("breaths", []) if not b.get("excluded")]
    lines = [
        f"Session: {payload.get('session', '')}",
        f"Detected pattern (pipeline): {payload['detected_pattern']} "
        f"(lifter/rotator gate = {payload['gate_threshold_deg']}° mean Δpitch)",
    ]
    if payload.get("archetype"):
        lines.append(
            f"Synthetic ground-truth archetype: {payload['archetype']} "
            "(the pipeline never saw this label — provided only as context that "
            "this is synthetic data)"
        )
    lines += [
        "",
        "Trial metrics (already computed — do not recompute):",
        f"  mean Δpitch on the breath : {s['mean_d_pitch_breath']}°   (gate {payload['gate_threshold_deg']}°)",
        f"  mean peak roll on the breath: {s['mean_peak_roll_breath']}°",
        f"  roll:pitch ratio           : {s['mean_roll_pitch_ratio']}  (dimensionless, secondary)",
        f"  breath-to-breath pitch SD  : {s['pitch_variability']}°",
        f"  asymmetry index            : {s['asymmetry_index']}  ((left − right) / mean Δpitch; +ve = left breath bigger)",
        f"  valid breaths              : {s['n_valid']} of {s['n_breaths']} ({s['n_excluded']} excluded by protocol)",
        f"  quality flags              : {', '.join(payload.get('flags', [])) or 'none'}",
    ]
    if valid:
        lines.append("")
        lines.append("Per valid breath (t_start s, side, Δpitch°, peak_roll°) — for drift/asymmetry reasoning:")
        for b in valid:
            lines.append(
                f"  t={b.get('t_start')}  {b.get('side')}  "
                f"Δpitch={b.get('d_pitch_breath')}  roll={b.get('peak_roll_breath')}"
            )
    lines += [
        "",
        f"Drill menu (choose from these names only): {', '.join(DRILL_MENU)}",
    ]
    return "\n".join(lines)


def narrate_payload(payload: dict, *, model: str = "claude-opus-5",
                    api_key: str | None = None, effort: str = "low",
                    lang: str = "en") -> dict:
    """Call Claude to produce a grounded interpretation for one swimmer payload.

    Returns a dict ``{summary, corrections, drills, model, lang}`` ready to attach
    to the payload as ``payload["narrative"]``. ``lang`` selects the output
    language ("en" default, "he" for Hebrew) — only the prose changes; the fact
    table and metric citations stay as computed. Raises on any failure (missing
    SDK, missing key, API error, refusal) so the caller can fall back cleanly.
    """
    try:
        import anthropic
    except ImportError as e:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "The 'anthropic' package is not installed. Run: pip install anthropic"
        ) from e

    client = anthropic.Anthropic(api_key=api_key)  # reads ANTHROPIC_API_KEY if None

    resp = client.messages.create(
        model=model,
        max_tokens=2000,
        system=_SYSTEM + _LANG_INSTRUCTION.get(lang, ""),
        output_config={"format": {"type": "json_schema", "schema": _SCHEMA},
                       "effort": effort},
        messages=[{"role": "user", "content": _fact_table(payload)}],
    )

    if resp.stop_reason == "refusal":  # guard before reading content
        raise RuntimeError(
            "Model declined to answer "
            f"({getattr(resp.stop_details, 'category', None)}); "
            "keeping the rule-based text."
        )

    text = next((b.text for b in resp.content if b.type == "text"), None)
    if not text:
        raise RuntimeError("No text block in the response.")
    data = json.loads(text)  # schema-constrained, so this parses
    data["model"] = resp.model
    data["lang"] = lang
    return data
