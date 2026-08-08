"""Placement-aware, rule-based findings in English **and** Hebrew.

Every placement gets the same structure as the LLM narration -- a plain
``headline``, a short ``summary``, and grounded ``coaching`` points that each
cite the metric they rest on -- generated deterministically from the computed
metrics, so the holistic app shows uniform "summary -> coaching" depth for head /
sacrum / wrist in either language with **no API call**.

Bilingual, single-source: each generator decides *which* message applies (from
the metrics) and returns language-neutral **codes + params**; the templates below
render each code into English and Hebrew. So the two languages can never drift in
which points they make. Following the project's narration convention
(``narrate.py``): the Hebrew addresses the swimmer in the **masculine singular**
(גוף שני, זכר יחיד) as the neutral default, and the grounding ``metric`` strings
(numbers, units, symbols) stay identical across languages.

Grounding discipline matches ``narrate.py``: interpret only computed metrics,
never recompute, and hedge everything -- a pre-validation research prototype, not
a validated finding. The thresholds that pick which point applies are
illustrative demo cues, deliberately kept in this viewer layer, not the engine.
"""

from __future__ import annotations

# side word per language
_SIDE = {"en": {"R": "right", "L": "left"}, "he": {"R": "ימין", "L": "שמאל"}}

# code -> {en: fn(params)->str, he: fn(params)->str}
_T = {
    # ---- head ----
    "head.lifts": {"en": lambda p: "Lifts the head to breathe",
                   "he": lambda p: "מרים את הראש כדי לנשום"},
    "head.rotates": {"en": lambda p: "Rotates to breathe, with little head lift",
                     "he": lambda p: "מסתובב לנשימה עם הרמת ראש מועטה"},
    "head.sum_lift": {
        "en": lambda p: f"The head rises about {p['dp']:.0f}° on the breath, past the "
                        f"~{p['gate']:.0f}° lifter/rotator line — consistent with lifting to "
                        "breathe, which tends to drop the hips and add drag.",
        "he": lambda p: f"הראש עולה בכ-{p['dp']:.0f}° בנשימה, מעבר לקו ~{p['gate']:.0f}° שמפריד "
                        "בין מרים למסתובב — עקבי עם הרמת ראש לנשימה, שנוטה להשקיע את האגן ולהוסיף גרר."},
    "head.sum_rot": {
        "en": lambda p: f"The head stays fairly level on the breath (~{p['dp']:.0f}°, under the "
                        f"~{p['gate']:.0f}° line) while the body rolls ~{p['roll']:.0f}° — consistent "
                        "with rotating to breathe, the pattern the study treats as efficient.",
        "he": lambda p: f"הראש נשאר יחסית מאוזן בנשימה (~{p['dp']:.0f}°, מתחת לקו ~{p['gate']:.0f}°) "
                        f"בעוד הגוף מסתובב ~{p['roll']:.0f}° — עקבי עם סיבוב לנשימה, הדפוס שהמחקר רואה כיעיל."},
    "head.trade": {
        "en": lambda p: "Trade lift for rotation — let the body roll open the mouth to air "
                        "instead of raising the head.",
        "he": lambda p: "המר הרמה בסיבוב — תן לגוף להסתובב ולפתוח את הפה לאוויר במקום להרים את הראש."},
    "head.roll_more": {
        "en": lambda p: "Roll a touch more toward the breathing side so the head can stay low.",
        "he": lambda p: "הסתובב מעט יותר לצד הנשימה כדי שהראש יישאר נמוך."},
    "head.asym": {
        "en": lambda p: f"The {p['side']} breath lifts more than the other side — even it out, or "
                        "practise breathing bilaterally.",
        "he": lambda p: f"הנשימה לצד {p['side']} מרימה יותר מהצד השני — אזן ביניהם, או תרגל נשימה דו-צדדית."},
    "head.consistency": {
        "en": lambda p: "Breath-to-breath consistency is variable — groove one repeatable pattern "
                        "rather than several.",
        "he": lambda p: "העקביות בין נשימה לנשימה משתנה — החדר דפוס אחד חוזר במקום כמה."},
    "head.efficient": {
        "en": lambda p: "Breathing looks efficient — keep the head low and roll to air.",
        "he": lambda p: "הנשימה נראית יעילה — שמור על ראש נמוך והסתובב לאוויר."},

    # ---- sacrum ----
    "sac.favours": {"en": lambda p: f"Body roll favours the {p['side']} side",
                    "he": lambda p: f"סיבוב הגוף נוטה לצד {p['side']}"},
    "sac.flat": {"en": lambda p: "Rolls flat — limited body rotation",
                 "he": lambda p: "סיבוב שטוח — רוטציית גוף מוגבלת"},
    "sac.balanced_h": {"en": lambda p: "Balanced, well-rotated body roll",
                       "he": lambda p: "סיבוב גוף מאוזן ומלא"},
    "sac.sum": {
        "en": lambda p: f"The body rolls about {p['roll']:.0f}° each stroke at a tempo of "
                        f"{p['tempo']:.0f} strokes/min. " + (
                        "Left and right rolls are well matched." if p["bal"]
                        else f"There is a lean toward the {p['side']} side ({p['sym']:+.2f} symmetry index)."),
        "he": lambda p: f"הגוף מסתובב כ-{p['roll']:.0f}° בכל תנועה בקצב של {p['tempo']:.0f} תנועות לדקה. " + (
                        "סיבובי ימין ושמאל תואמים היטב." if p["bal"]
                        else f"יש נטייה לצד {p['side']} (מדד סימטריה {p['sym']:+.2f})."),
    },
    "sac.uneven": {
        "en": lambda p: f"Roll is uneven — you rotate further to the {p['side']}. Work the weaker "
                        "side (single-side drills, balanced breathing) to even it out.",
        "he": lambda p: f"הסיבוב לא אחיד — אתה מסתובב יותר ל{p['side']}. חזק את הצד החלש "
                        "(תרגילי צד אחד, נשימה מאוזנת) כדי לאזן."},
    "sac.limited": {
        "en": lambda p: "Limited body roll — rotate more from the hips so each arm can catch "
                        "deeper water.",
        "he": lambda p: "סיבוב גוף מוגבל — הסתובב יותר מהאגן כדי שכל יד תתפוס מים עמוקים יותר."},
    "sac.excess": {
        "en": lambda p: "Very large roll — over-rotating can stall the stroke; aim for a steadier, "
                        "controlled rotation.",
        "he": lambda p: "סיבוב גדול מאוד — סיבוב יתר עלול לעצור את התנועה; כוון לרוטציה יציבה ומבוקרת."},
    "sac.pace": {
        "en": lambda p: "Pace fades across the swim — hold tempo on the back half with a tempo "
                        "trainer or a steady count.",
        "he": lambda p: "הקצב נחלש לאורך השחייה — שמור על טמפו בחצי השני עם שעון קצב או ספירה קבועה."},
    "sac.ok": {
        "en": lambda p: "Roll and tempo look balanced — keep the rotation symmetric as you add speed.",
        "he": lambda p: "הסיבוב והקצב נראים מאוזנים — שמור על רוטציה סימטרית ככל שאתה מגביר מהירות."},

    # ---- wrist ----
    "wr.dominant": {"en": lambda p: f"The {p['side']} arm does more of the work",
                    "he": lambda p: f"יד {p['side']} עושה יותר מהעבודה"},
    "wr.matched_h": {"en": lambda p: "Left and right arms are well matched",
                     "he": lambda p: "היד הימנית והשמאלית מאוזנות"},
    "wr.sum": {
        "en": lambda p: f"The right forearm sweeps ~{p['r']:.0f}° through the pull and the left "
                        f"~{p['l']:.0f}°. " + ("The two arms are balanced and alternate cleanly "
                        "(antiphase)." if p["bal"] else f"The {p['side']} arm pulls with a noticeably "
                        "bigger sweep."),
        "he": lambda p: f"האמה הימנית מטאטאת ~{p['r']:.0f}° במשיכה והשמאלית ~{p['l']:.0f}°. " + (
                        "שתי הידיים מאוזנות ומתחלפות נקי (אנטי-פאזה)." if p["bal"]
                        else f"יד {p['side']} מושכת בטווח גדול יותר."),
    },
    "wr.uneven": {
        "en": lambda p: f"Arm pull is uneven — the {p['side']} arm sweeps more. Strengthen the "
                        f"{p['weak']} catch (single-arm drills on the {p['weak']}).",
        "he": lambda p: f"משיכת הידיים לא אחידה — יד {p['side']} מטאטאת יותר. חזק את התפיסה של "
                        f"יד {p['weak']} (תרגילי יד אחת ל{p['weak']})."},
    "wr.stroke_diff": {
        "en": lambda p: "The two arms take a different number of strokes — check for a stalled catch "
                        "on the slower side.",
        "he": lambda p: "הידיים לוקחות מספר תנועות שונה — בדוק תפיסה תקועה בצד האיטי."},
    "wr.phase": {
        "en": lambda p: "Arm timing is off antiphase — one hand should enter as the other finishes "
                        "the pull; smooth the crossover.",
        "he": lambda p: "התזמון בין הידיים חורג מאנטי-פאזה — יד אחת צריכה להיכנס כשהשנייה מסיימת "
                        "את המשיכה; החלק את המעבר."},
    "wr.pull_short": {
        "en": lambda p: "The propulsive pull is a short part of the cycle — lengthen time on the "
                        "catch rather than rushing to recovery.",
        "he": lambda p: "המשיכה המניעה היא חלק קצר מהמחזור — הארך את הזמן על התפיסה במקום למהר להתאוששות."},
    "wr.ok": {
        "en": lambda p: "Both arms are balanced and well-timed — maintain the even catch as you fatigue.",
        "he": lambda p: "שתי הידיים מאוזנות ומתוזמנות היטב — שמור על תפיסה אחידה גם בעייפות."},
}


def _render(neutral: dict, lang: str) -> dict:
    """Render a language-neutral findings spec into one language."""
    def txt(code, params):
        p = dict(params)
        if "side_key" in p:
            p["side"] = _SIDE[lang][p.pop("side_key")]
        if "weak_key" in p:
            p["weak"] = _SIDE[lang][p.pop("weak_key")]
        return _T[code][lang](p)

    return {
        "headline": txt(*neutral["headline"]),
        "summary": txt(*neutral["summary"]),
        "coaching": [{"point": txt(c["code"], c.get("params", {})), "metric": c["metric"]}
                     for c in neutral["coaching"]],
    }


# --------------------------------------------------------------------------- #
# Placement generators (language-neutral: choose codes + params + metric)
# --------------------------------------------------------------------------- #


def _head(p: dict) -> dict:
    s = p["summary"]; dp = s.get("mean_d_pitch_breath"); gate = p.get("gate_threshold_deg", 13.5)
    roll = s.get("mean_peak_roll_breath"); asym = s.get("asymmetry_index"); sd = s.get("pitch_variability")
    lifts = dp is not None and dp > gate
    co = []
    if lifts:
        co.append({"code": "head.trade", "metric": f"mean Δpitch {dp:.1f}° vs {gate:.0f}° gate"})
        if roll is not None and roll < 40:
            co.append({"code": "head.roll_more", "metric": f"peak roll {roll:.0f}°"})
    if asym is not None and abs(asym) > 0.25:
        co.append({"code": "head.asym", "params": {"side_key": "L" if asym > 0 else "R"},
                   "metric": f"asymmetry index {asym:+.2f}"})
    if sd is not None and sd > 6:
        co.append({"code": "head.consistency", "metric": f"pitch SD {sd:.1f}°"})
    if not co:
        co.append({"code": "head.efficient", "metric": f"mean Δpitch {dp:.1f}° under the {gate:.0f}° gate"})
    return {
        "placement": "head",
        "headline": ("head.lifts" if lifts else "head.rotates", {}),
        "summary": ("head.sum_lift" if lifts else "head.sum_rot",
                    {"dp": dp, "gate": gate, "roll": roll}),
        "coaching": co,
    }


def _sacrum(p: dict) -> dict:
    s = p["summary"]; roll = s.get("body_roll_amplitude_deg"); sym = s.get("roll_symmetry_index") or 0.0
    tempo = s.get("tempo_spm"); drift = s.get("pace_drift_s_per_length")
    strong = "R" if sym > 0 else "L"; bal = abs(sym) < 0.1
    if abs(sym) > 0.15:
        headline = ("sac.favours", {"side_key": strong})
    elif roll is not None and roll < 35:
        headline = ("sac.flat", {})
    else:
        headline = ("sac.balanced_h", {})
    co = []
    if abs(sym) > 0.15:
        co.append({"code": "sac.uneven", "params": {"side_key": strong},
                   "metric": f"roll symmetry {sym:+.2f} ({_SIDE['en'][strong]}-dominant)"})
    if roll is not None and roll < 35:
        co.append({"code": "sac.limited", "metric": f"body-roll amplitude {roll:.0f}°"})
    if roll is not None and roll > 60:
        co.append({"code": "sac.excess", "metric": f"body-roll amplitude {roll:.0f}°"})
    if drift is not None and drift > 0.1:
        co.append({"code": "sac.pace", "metric": f"pace drift {drift:+.2f} s/length"})
    if not co:
        co.append({"code": "sac.ok", "metric": f"roll {roll:.0f}°, symmetry {sym:+.2f}"})
    return {
        "placement": "sacrum", "headline": headline,
        "summary": ("sac.sum", {"roll": roll, "tempo": tempo, "sym": sym, "bal": bal, "side_key": strong}),
        "coaching": co,
    }


def _wrist(p: dict) -> dict:
    R = p["arms"]["R"]["summary"]; L = p["arms"]["L"]["summary"]; sy = p.get("symmetry", {})
    amp = sy.get("amplitude_symmetry_index") or 0.0; phase = sy.get("mean_phase_offset_cycles")
    strong = "R" if amp > 0 else "L"; weak = "L" if strong == "R" else "R"; bal = abs(amp) < 0.1
    headline = ("wr.dominant", {"side_key": strong}) if abs(amp) > 0.15 else ("wr.matched_h", {})
    co = []
    if abs(amp) > 0.15:
        co.append({"code": "wr.uneven", "params": {"side_key": strong, "weak_key": weak},
                   "metric": f"amplitude symmetry {amp:+.2f} ({_SIDE['en'][strong]}-dominant)"})
    if abs((R.get("stroke_count") or 0) - (L.get("stroke_count") or 0)) > 2:
        co.append({"code": "wr.stroke_diff",
                   "metric": f"strokes R {R.get('stroke_count')} vs L {L.get('stroke_count')}"})
    if phase is not None and abs(phase - 0.5) > 0.12:
        co.append({"code": "wr.phase", "metric": f"phase offset {phase:.2f} cycles (0.5 = antiphase)"})
    pf = R.get("pull_fraction")
    if pf is not None and pf < 0.2:
        co.append({"code": "wr.pull_short", "metric": f"pull fraction {pf:.2f} of the cycle"})
    if not co:
        co.append({"code": "wr.ok", "metric": f"amplitude symmetry {amp:+.2f}, phase {phase:.2f}"})
    return {
        "placement": "wrist", "headline": headline,
        "summary": ("wr.sum", {"r": R.get("pitch_amplitude_deg", 0), "l": L.get("pitch_amplitude_deg", 0),
                    "bal": bal, "side_key": strong}),
        "coaching": co,
    }


def findings_for(payload: dict) -> dict:
    """Bilingual ``{en:{headline,summary,coaching[]}, he:{...}, placement}``.

    Detects the placement from the payload shape, builds one language-neutral
    spec, and renders it into English and Hebrew. ``coaching`` items are
    ``{point, metric}`` -- the point translates, the metric citation stays
    identical across languages.
    """
    if "arms" in payload:
        neutral = _wrist(payload)
    elif "body_roll_amplitude_deg" in payload.get("summary", {}):
        neutral = _sacrum(payload)
    elif "mean_d_pitch_breath" in payload.get("summary", {}):
        neutral = _head(payload)
    else:
        return {"placement": "unknown", "en": {"headline": "", "summary": "", "coaching": []},
                "he": {"headline": "", "summary": "", "coaching": []}}
    return {"placement": neutral["placement"],
            "en": _render(neutral, "en"), "he": _render(neutral, "he")}
