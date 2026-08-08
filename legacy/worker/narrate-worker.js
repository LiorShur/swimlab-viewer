/**
 * swimlab-viewer — live narration proxy (Cloudflare Worker), placement-aware.
 *
 * GitHub Pages is static: a public page can't hold the Anthropic key without
 * leaking it. This Worker holds the key server-side, accepts a session's
 * *already-computed* metrics for ANY sensor placement (head / sacrum / wrist),
 * calls Claude, and returns the same narrative shape `src/narrate.py` produces
 * offline. The static page fetch()es this endpoint on demand.
 *
 * The deterministic pipeline (calibrate -> events -> metrics) is never in the
 * loop — Claude only rewrites the interpretation layer, from a fixed per-placement
 * fact table. This file is a straight port of src/narrate.py; keep BASE_SYSTEM,
 * GUIDE, the fact tables and the schema in sync with it.
 *
 * Secrets / config:
 *   ANTHROPIC_API_KEY  (secret, required)  — never sent to the browser
 *   ALLOWED_ORIGIN     (var, recommended)  — e.g. https://liorshur.github.io
 *   SHARED_SECRET      (secret, optional)  — require header X-Narrate-Key to match
 *   NARRATE_MODEL      (var, optional)     — default "claude-opus-5"
 *   NARRATE_THINKING   (var, optional)     — "auto" | "on" | "off"
 */

const DRILL_MENU = [
  "Single-arm freestyle",
  "6-kick / 3-stroke switch",
  "“One goggle out” cue",
  "Exhale-pattern breathing",
  "Bilateral breathing (every 3)",
  "Tempo-trainer breathing",
  "Side-kick balance (kick on your side)",
  "Steady-state sets with a low-head cue",
];

const BASE_SYSTEM = `You write the interpretation section of a swim-technique \
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
(each with its grounding metric).{DRILLS}

2. A SWIMMER layer (plain): for the recreational swimmer themselves, not a coach.
- headline: ONE short sentence, ~10 words max, NO metric names and NO numbers, \
saying in plain terms what their technique does.
- swimmer_summary: 2 short sentences, warm and encouraging, explaining what it \
means and why it matters — still no jargon, no numbers, no degrees.
- swimmer_actions: 2–3 very short, concrete things to try, in plain language a \
swimmer can act on in the water (no metric talk).

Keep the two layers consistent with each other and with the metrics.

Placement context:
{GUIDE}`;

const DRILLS_CLAUSE =
  " Then 3–5 drills (each with a swimmer-specific reason), chosen ONLY from the " +
  'menu given in the fact table; keep the names recognisable and tailor the "why" ' +
  "to this swimmer.";

const GUIDE = {
  head:
    "This sensor is on the HEAD (skull). It measures breath technique: whether the " +
    "swimmer lifts the head (Δpitch) or rotates to breathe (roll). The lifter/rotator " +
    "gate is mean Δpitch vs the gate value; lifting the head drops the hips and adds " +
    "drag, while rotating to breathe is the efficient pattern the study favours. The " +
    "asymmetry index relates to the breathing side; the pitch SD is breath-to-breath " +
    "consistency; pitch drift is fatigue across the swim.",
  sacrum:
    "This sensor is on the SACRUM (pelvis). It measures whole-body roll and the wall " +
    "push-offs: lengths, distance, stroke count, tempo/stroke rate, body-roll amplitude, " +
    "LEFT/RIGHT roll symmetry, push-off count/interval and pace drift. Efficient " +
    "freestyle has ample, symmetric body roll and steady pace; a clear L/R roll " +
    "asymmetry, very little (or excessive) roll, or a pace that fades across lengths is " +
    "worth flagging. Distance is lengths × pool length — an IMU cannot measure position.",
  wrist:
    "This sensor is on the WRIST (forearm) — one per arm. It measures each arm's stroke " +
    "phases from forearm pitch: stroke count/rate, pull duration and the pull fraction " +
    "of the cycle, and pitch amplitude (the arc the hand sweeps from the over-water " +
    "recovery down to the catch). The FUSION of the two arms gives left/right symmetry " +
    "(amplitude, stroke count, pull duration) and the phase offset (≈0.5 cycles = clean " +
    "antiphase, one hand entering as the other finishes the pull). Flag a dominant arm, " +
    "uneven stroke counts, or timing that drifts off antiphase.",
};

const TRANSLATE_INSTRUCTION =
  "\n\nReturn BOTH languages in one object. First write the full interpretation " +
  "in English as the `en` object (the COACH + SWIMMER layers specified above). " +
  "Then write `he`: a faithful, natural Hebrew translation of every field in " +
  "`en` — it must say the same things, only in fluent Hebrew. In `he`, address " +
  "the swimmer in the masculine singular (Hebrew גוף שני, זכר יחיד) consistently " +
  "and never switch to feminine forms; translate any drill names into Hebrew; but " +
  'keep every "metric" string and all numbers, units and symbols exactly as in `en`.';

function correctionSchema() {
  return {
    type: "array",
    items: {
      type: "object",
      additionalProperties: false,
      properties: { point: { type: "string" }, metric: { type: "string" } },
      required: ["point", "metric"],
    },
  };
}

function schemaFor(placement) {
  const properties = {
    headline: { type: "string" },
    swimmer_summary: { type: "string" },
    swimmer_actions: { type: "array", items: { type: "string" } },
    summary: { type: "string" },
    corrections: correctionSchema(),
  };
  const required = ["headline", "swimmer_summary", "swimmer_actions", "summary", "corrections"];
  if (placement === "head") {
    properties.drills = {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        properties: { name: { type: "string" }, why: { type: "string" } },
        required: ["name", "why"],
      },
    };
    required.push("drills");
  }
  return { type: "object", additionalProperties: false, properties, required };
}

function detectPlacement(payload) {
  if (["head", "sacrum", "wrist"].includes(payload.placement)) return payload.placement;
  if (payload.arms) return "wrist";
  const s = payload.summary || {};
  if (s.body_roll_amplitude_deg != null) return "sacrum";
  if (s.mean_d_pitch_breath != null) return "head";
  return "head";
}

function systemPrompt(placement) {
  return BASE_SYSTEM.replace("{DRILLS}", placement === "head" ? DRILLS_CLAUSE : "")
    .replace("{GUIDE}", GUIDE[placement] || GUIDE.head);
}

const flagsStr = (p) => (p.flags && p.flags.length ? p.flags.join(", ") : "none");

function headFacts(payload) {
  const s = payload.summary;
  const valid = (Array.isArray(payload.breaths) ? payload.breaths : []).filter((b) => !b.excluded);
  const lines = [
    `Session: ${payload.session || ""}`,
    "Placement: HEAD (skull)",
    `Detected pattern (pipeline): ${payload.detected_pattern} ` +
      `(lifter/rotator gate = ${payload.gate_threshold_deg}° mean Δpitch)`,
  ];
  if (payload.archetype)
    lines.push(`Synthetic ground-truth archetype: ${payload.archetype} (context only)`);
  lines.push(
    "",
    "Trial metrics (already computed — do not recompute):",
    `  mean Δpitch on the breath : ${s.mean_d_pitch_breath}°   (gate ${payload.gate_threshold_deg}°)`,
    `  mean peak roll on the breath: ${s.mean_peak_roll_breath}°`,
    `  roll:pitch ratio           : ${s.mean_roll_pitch_ratio}  (dimensionless, secondary)`,
    `  breath-to-breath pitch SD  : ${s.pitch_variability}°`,
    `  asymmetry index            : ${s.asymmetry_index}  ((left − right) / mean Δpitch; +ve = left breath bigger)`,
    `  valid breaths              : ${s.n_valid} of ${s.n_breaths} (${s.n_excluded} excluded by protocol)`,
    `  quality flags              : ${flagsStr(payload)}`
  );
  if (valid.length) {
    lines.push("", "Per valid breath (t_start s, side, Δpitch°, peak_roll°):");
    for (const b of valid)
      lines.push(`  t=${b.t_start}  ${b.side}  Δpitch=${b.d_pitch_breath}  roll=${b.peak_roll_breath}`);
  }
  lines.push("", `Drill menu (choose from these names only): ${DRILL_MENU.join(", ")}`);
  return lines.join("\n");
}

function sacrumFacts(payload) {
  const s = payload.summary;
  const lines = [`Session: ${payload.session || ""}`, "Placement: SACRUM (pelvis)"];
  if (payload.archetype)
    lines.push(`Synthetic ground-truth archetype: ${payload.archetype} (context only)`);
  lines.push(
    "",
    "Trial metrics (already computed — do not recompute):",
    `  lengths                    : ${s.lengths}`,
    `  distance                   : ${s.distance_m} m  (= lengths × pool length; no position from an IMU)`,
    `  stroke count               : ${s.stroke_count} (${s.n_valid_strokes} valid)`,
    `  tempo                      : ${s.tempo_spm} strokes/min`,
    `  stroke rate                : ${s.stroke_rate_cpm} cycles/min`,
    `  body-roll amplitude        : ${s.body_roll_amplitude_deg}°`,
    `  mean peak roll right/left  : ${s.mean_peak_roll_right_deg}° / ${s.mean_peak_roll_left_deg}°`,
    `  roll symmetry index        : ${s.roll_symmetry_index}  ((right − left)/mean; +ve = rolls further right)`,
    `  push-offs                  : ${s.pushoff_count} (mean interval ${s.mean_pushoff_interval_s} s)`,
    `  pace drift                 : ${s.pace_drift_s_per_length} s/length  (+ve = slowing across the swim)`,
    `  quality flags              : ${flagsStr(payload)}`
  );
  return lines.join("\n");
}

function wristFacts(payload) {
  const R = payload.arms.R.summary, L = payload.arms.L.summary, sy = payload.symmetry || {};
  const lines = [`Session: ${payload.session || ""}`, "Placement: WRIST (forearm, left + right)"];
  if (payload.archetype)
    lines.push(`Synthetic ground-truth archetype: ${payload.archetype} (context only)`);
  lines.push(
    "",
    "Per-arm metrics (already computed — do not recompute):",
    `  RIGHT: strokes ${R.stroke_count} (${R.n_valid_strokes} valid), rate ${R.stroke_rate_cpm} cyc/min, ` +
      `pitch amplitude ${R.pitch_amplitude_deg}°, mean pull ${R.mean_pull_duration_s} s, pull fraction ${R.pull_fraction} of the cycle`,
    `  LEFT : strokes ${L.stroke_count} (${L.n_valid_strokes} valid), rate ${L.stroke_rate_cpm} cyc/min, ` +
      `pitch amplitude ${L.pitch_amplitude_deg}°, mean pull ${L.mean_pull_duration_s} s, pull fraction ${L.pull_fraction} of the cycle`,
    "",
    "Left/right symmetry (fusion; each index = (R − L)/mean, 0 = symmetric):",
    `  amplitude symmetry index   : ${sy.amplitude_symmetry_index}`,
    `  stroke-count symmetry index: ${sy.stroke_count_symmetry_index}`,
    `  pull-duration symmetry idx : ${sy.pull_duration_symmetry_index}`,
    `  phase offset               : ${sy.mean_phase_offset_cycles} cycles  (0.5 = clean antiphase)`,
    `  quality flags              : ${flagsStr(payload)}`
  );
  return lines.join("\n");
}

const FACTS = { head: headFacts, sacrum: sacrumFacts, wrist: wristFacts };

function isSwimPayload(payload) {
  if (!payload || typeof payload !== "object") return false;
  if (payload.arms) return true;                    // wrist
  const s = payload.summary;
  return !!(s && (s.mean_d_pitch_breath != null || s.body_roll_amplitude_deg != null));
}

function corsHeaders(origin, allowed) {
  const allow = allowed === "*" ? "*" : allowed;
  return {
    "Access-Control-Allow-Origin": allow,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-Narrate-Key",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
}

function json(body, status, cors) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...cors },
  });
}

export default {
  async fetch(request, env) {
    const allowed = env.ALLOWED_ORIGIN || "*";
    const origin = request.headers.get("Origin") || "";
    const cors = corsHeaders(origin, allowed);

    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    if (request.method !== "POST") return json({ error: "POST only" }, 405, cors);
    if (allowed !== "*" && origin && origin !== allowed)
      return json({ error: "origin not allowed" }, 403, cors);
    if (env.SHARED_SECRET && request.headers.get("X-Narrate-Key") !== env.SHARED_SECRET)
      return json({ error: "unauthorized" }, 401, cors);
    if (!env.ANTHROPIC_API_KEY) return json({ error: "server missing ANTHROPIC_API_KEY" }, 500, cors);

    let payload;
    try {
      const raw = await request.text();
      if (raw.length > 200_000) return json({ error: "payload too large" }, 413, cors);
      payload = JSON.parse(raw);
    } catch {
      return json({ error: "invalid JSON body" }, 400, cors);
    }
    if (!isSwimPayload(payload))
      return json({ error: "not a swimlab session payload" }, 400, cors);

    const placement = detectPlacement(payload);
    const model = env.NARRATE_MODEL || "claude-opus-5";
    const system = systemPrompt(placement) + TRANSLATE_INSTRUCTION;
    const dualSchema = {
      type: "object",
      additionalProperties: false,
      properties: { en: schemaFor(placement), he: schemaFor(placement) },
      required: ["en", "he"],
    };

    const output_config = { format: { type: "json_schema", schema: dualSchema } };
    if (!/haiku/i.test(model)) output_config.effort = "low";

    const reqBody = {
      model,
      max_tokens: 3600,
      system,
      output_config,
      messages: [{ role: "user", content: FACTS[placement](payload) }],
    };
    const thinkPref = (env.NARRATE_THINKING || "auto").toLowerCase();
    const isHaiku = /haiku/i.test(model);
    if (thinkPref === "off") {
      if (!/fable|mythos/i.test(model)) reqBody.thinking = { type: "disabled" };
    } else if (!isHaiku) {
      reqBody.thinking = { type: "adaptive" };
    }

    let apiResp;
    try {
      apiResp = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-api-key": env.ANTHROPIC_API_KEY,
          "anthropic-version": "2023-06-01",
        },
        body: JSON.stringify(reqBody),
      });
    } catch (e) {
      return json({ error: "upstream fetch failed: " + e.message }, 502, cors);
    }
    if (!apiResp.ok) {
      const detail = await apiResp.text();
      return json({ error: `anthropic ${apiResp.status}`, detail }, 502, cors);
    }

    const data = await apiResp.json();
    if (data.stop_reason === "refusal")
      return json({ error: "model declined; keep the rule-based text" }, 502, cors);
    const textBlock = (data.content || []).find((b) => b.type === "text");
    if (!textBlock) return json({ error: "no text block in response" }, 502, cors);

    let parsed;
    try {
      parsed = JSON.parse(textBlock.text);
    } catch {
      return json({ error: "model output was not valid JSON" }, 502, cors);
    }
    // Uniform envelope: { narratives: { en, he }, model, placement }.
    return json(
      { narratives: { en: parsed.en, he: parsed.he }, model: data.model || model, placement },
      200,
      cors
    );
  },
};
