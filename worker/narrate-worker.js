/**
 * swimlab-viewer — live narration proxy (Cloudflare Worker).
 *
 * GitHub Pages is static: a public page can't hold the Anthropic key without
 * leaking it. This Worker holds the key server-side, accepts a session's
 * *already-computed* metrics, calls Claude, and returns the same
 * {summary, corrections, drills, model} narrative that `src/narrate.py`
 * produces offline. The static page fetch()es this endpoint on demand.
 *
 * The deterministic pipeline (calibrate -> events -> metrics -> stats) is never
 * in the loop here — Claude only rewrites the interpretation layer, from a fixed
 * fact table, exactly as the offline path does. This file is a straight port of
 * src/narrate.py; keep the SYSTEM prompt, SCHEMA, DRILL_MENU and factTable() in
 * sync with it so live and baked narratives read the same.
 *
 * Secrets / config (set with `wrangler secret put` / in wrangler.toml [vars]):
 *   ANTHROPIC_API_KEY   (secret, required)  — never sent to the browser
 *   ALLOWED_ORIGIN      (var, recommended)  — e.g. https://liorshur.github.io
 *                                             CORS-allow only this origin. "*" = any (dev only).
 *   SHARED_SECRET       (secret, optional)  — if set, require header X-Narrate-Key to match
 *   NARRATE_MODEL       (var, optional)     — default "claude-opus-5"
 */

// The app's canonical drill vocabulary (mirrors DRILL in template.html / narrate.py).
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

const SYSTEM = `You write the interpretation section of a swim-technique analysis \
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

Keep the two layers consistent with each other and with the metrics.`;

// Language addendum. The fact table and metric names stay as given; only the
// prose Claude writes changes language. Mirror this in narrate.py.
const LANG_INSTRUCTION = {
  he:
    "\n\nWrite ALL prose you produce in natural Hebrew — both layers: the " +
    "headline, swimmer_summary and swimmer_actions (plain, warm, everyday " +
    "Hebrew for a swimmer), and the coach summary, every correction \"point\", " +
    "and every drill \"name\" and \"why\". Address the swimmer in the masculine " +
    "singular (Hebrew גוף שני, זכר יחיד) consistently throughout — the swimmer's " +
    "gender is unknown, so use masculine as the neutral default and never switch " +
    "to feminine forms. Keep the grounding \"metric\" strings and all numbers, " +
    "units and symbols (e.g. Δpitch, °, the gate value) exactly as in the fact " +
    "table. Pick drills from the English menu but translate the chosen name into " +
    "Hebrew.",
};

const SCHEMA = {
  type: "object",
  additionalProperties: false,
  properties: {
    headline: { type: "string" },
    swimmer_summary: { type: "string" },
    swimmer_actions: { type: "array", items: { type: "string" } },
    summary: { type: "string" },
    corrections: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        properties: {
          point: { type: "string" },
          metric: { type: "string" },
        },
        required: ["point", "metric"],
      },
    },
    drills: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        properties: {
          name: { type: "string" },
          why: { type: "string" },
        },
        required: ["name", "why"],
      },
    },
  },
  required: ["headline", "swimmer_summary", "swimmer_actions",
             "summary", "corrections", "drills"],
};

/** Render the payload's metrics as a compact fact table — port of narrate._fact_table. */
function factTable(payload) {
  const s = payload.summary;
  const breaths = Array.isArray(payload.breaths) ? payload.breaths : [];
  const valid = breaths.filter((b) => !b.excluded);
  const flags = (payload.flags && payload.flags.length) ? payload.flags.join(", ") : "none";

  const lines = [
    `Session: ${payload.session || ""}`,
    `Detected pattern (pipeline): ${payload.detected_pattern} ` +
      `(lifter/rotator gate = ${payload.gate_threshold_deg}° mean Δpitch)`,
  ];
  if (payload.archetype) {
    lines.push(
      `Synthetic ground-truth archetype: ${payload.archetype} ` +
        "(the pipeline never saw this label — provided only as context that " +
        "this is synthetic data)"
    );
  }
  lines.push(
    "",
    "Trial metrics (already computed — do not recompute):",
    `  mean Δpitch on the breath : ${s.mean_d_pitch_breath}°   (gate ${payload.gate_threshold_deg}°)`,
    `  mean peak roll on the breath: ${s.mean_peak_roll_breath}°`,
    `  roll:pitch ratio           : ${s.mean_roll_pitch_ratio}  (dimensionless, secondary)`,
    `  breath-to-breath pitch SD  : ${s.pitch_variability}°`,
    `  asymmetry index            : ${s.asymmetry_index}  ((left − right) / mean Δpitch; +ve = left breath bigger)`,
    `  valid breaths              : ${s.n_valid} of ${s.n_breaths} (${s.n_excluded} excluded by protocol)`,
    `  quality flags              : ${flags}`
  );
  if (valid.length) {
    lines.push("");
    lines.push("Per valid breath (t_start s, side, Δpitch°, peak_roll°) — for drift/asymmetry reasoning:");
    for (const b of valid) {
      lines.push(
        `  t=${b.t_start}  ${b.side}  Δpitch=${b.d_pitch_breath}  roll=${b.peak_roll_breath}`
      );
    }
  }
  lines.push("");
  lines.push(`Drill menu (choose from these names only): ${DRILL_MENU.join(", ")}`);
  return lines.join("\n");
}

function corsHeaders(origin, allowed) {
  // Echo the request origin only when it matches the allow-list (or "*").
  const allow = allowed === "*" ? "*" : (origin === allowed ? allowed : allowed);
  return {
    "Access-Control-Allow-Origin": allow,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-Narrate-Key",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
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

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }
    if (request.method !== "POST") {
      return json({ error: "POST only" }, 405, cors);
    }
    // Origin gate: browsers can't spoof Origin, so this blocks other websites'
    // pages from calling the Worker. (It does not stop a hand-rolled curl.)
    if (allowed !== "*" && origin && origin !== allowed) {
      return json({ error: "origin not allowed" }, 403, cors);
    }
    // Optional shared-secret gate — a light guard against random scripts hitting
    // the URL. On a fully public page the secret lives in the browser, so treat
    // it as friction, not real auth; pair with a Cloudflare rate-limit rule.
    if (env.SHARED_SECRET) {
      if (request.headers.get("X-Narrate-Key") !== env.SHARED_SECRET) {
        return json({ error: "unauthorized" }, 401, cors);
      }
    }
    if (!env.ANTHROPIC_API_KEY) {
      return json({ error: "server missing ANTHROPIC_API_KEY" }, 500, cors);
    }

    let payload;
    try {
      const raw = await request.text();
      if (raw.length > 200_000) return json({ error: "payload too large" }, 413, cors);
      payload = JSON.parse(raw);
    } catch {
      return json({ error: "invalid JSON body" }, 400, cors);
    }
    if (!payload || !payload.summary || !payload.detected_pattern) {
      return json({ error: "not a swimlab session payload" }, 400, cors);
    }

    // Model is configurable via NARRATE_MODEL (wrangler var) — the main speed
    // lever. Faster/cheaper models finish this bounded task in a few seconds:
    //   claude-haiku-4-5  — fastest, cheapest
    //   claude-sonnet-5   — near-Opus quality, faster than Opus
    //   claude-opus-5     — highest quality, slowest (default)
    const model = env.NARRATE_MODEL || "claude-opus-5";
    const lang = typeof payload.lang === "string" ? payload.lang : "en";
    const system = SYSTEM + (LANG_INSTRUCTION[lang] || "");

    const output_config = { format: { type: "json_schema", schema: SCHEMA } };
    // Haiku 4.5 rejects output_config.effort; every other current model accepts it.
    if (!/haiku/i.test(model)) output_config.effort = "low";

    const reqBody = {
      model,
      max_tokens: 2000,
      system,
      output_config,
      messages: [{ role: "user", content: factTable(payload) }],
    };
    // Thinking ON (adaptive) — the correct on-mode for Sonnet 5 / Opus 5
    // ({type:"enabled"} is rejected on these). Skip Haiku 4.5, which doesn't
    // take adaptive thinking and is fast without it.
    if (!/haiku/i.test(model)) reqBody.thinking = { type: "adaptive" };

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
    if (data.stop_reason === "refusal") {
      return json({ error: "model declined; keep the rule-based text" }, 502, cors);
    }
    const textBlock = (data.content || []).find((b) => b.type === "text");
    if (!textBlock) {
      return json({ error: "no text block in response" }, 502, cors);
    }

    let narrative;
    try {
      narrative = JSON.parse(textBlock.text); // schema-constrained, so this parses
    } catch {
      return json({ error: "model output was not valid JSON" }, 502, cors);
    }
    narrative.model = data.model || model;
    narrative.lang = lang;
    return json(narrative, 200, cors);
  },
};
