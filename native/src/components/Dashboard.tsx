import { useEffect, useMemo, useRef, useState } from "react";
import { BANNER, KPI_LABEL, KPI_UNIT, STR, type Lang } from "../lib/i18n";
import { PlaybackControls } from "./PlaybackControls";
import { TraceChart, type Series } from "./TraceChart";
import { Findings } from "./Findings";
import { Drills } from "./Drills";
import { MotionSchematic } from "./MotionSchematic";
import { PlacementDetails } from "./PlacementDetails";

const PALETTE = ["#4aa8ff", "#ff8a5b", "#3fb950", "#d29922"];

// Pull a {t, series[]} view out of whatever traces a placement payload carries
// (head: pitch/roll; sacrum: roll; wrist: per-arm pitch). Generic so every
// placement renders without bespoke code.
function extractTraces(session: any): { t: number[]; series: Series[] } {
  const tr = session?.traces || {};
  let t: number[] = Array.isArray(tr.t) ? tr.t : [];
  const series: Series[] = [];
  let ci = 0;
  const add = (name: string, data: any) => {
    if (Array.isArray(data) && data.length) series.push({ name, color: PALETTE[ci++ % PALETTE.length], data });
  };
  for (const [k, v] of Object.entries(tr)) {
    if (k === "t") continue;
    add(k, v);
  }
  // wrist payloads keep per-arm traces under arms.{R,L}
  if (!series.length && session?.arms) {
    for (const [side, arm] of Object.entries<any>(session.arms)) {
      if (Array.isArray(arm?.traces?.t) && !t.length) t = arm.traces.t;
      add(`pitch ${side}`, arm?.traces?.pitch);
    }
  }
  return { t, series };
}

function Kpis(props: { lang: Lang; summary: Record<string, any> }) {
  const entries = Object.entries(props.summary || {}).filter(
    ([, v]) => typeof v === "number" && Number.isFinite(v),
  );
  if (!entries.length) return null;
  const label = (k: string) => KPI_LABEL[props.lang][k] ?? k.replace(/_/g, " ");
  return (
    <div className="kpis">
      {entries.slice(0, 8).map(([k, v]) => (
        <div className="kpi" key={k}>
          <div className="k-lab">{label(k)}</div>
          <div className="k-val">
            {Number.isInteger(v) ? v : Number(v).toFixed(2)}
            {KPI_UNIT[k] && <span className="u"> {KPI_UNIT[k]}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

export function Dashboard(props: {
  lang: Lang;
  placement: string;
  session: any;
  onNarrate: (session: any) => Promise<void>;
  onGoCapture?: () => void;
}) {
  const t = (k: string) => STR[props.lang][k] ?? k;
  // Nudge toward the advanced (separate-calibration) path when a single-file
  // import couldn't be analysed — the usual cause is no calibration in the file.
  const flags: string[] = props.session?.flags || [];
  const incomplete = flags.includes("FINDINGS_INCOMPLETE") ||
    (flags.includes("CALIB_FROM_TRIAL_PROVISIONAL") && flags.includes("INSUFFICIENT_CYCLES"));
  const { t: times, series } = useMemo(() => extractTraces(props.session), [props.session]);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [narrating, setNarrating] = useState(false);
  const raf = useRef<number | null>(null);
  const last = useRef<number>(0);

  useEffect(() => { setIndex(0); setPlaying(false); }, [props.session]);

  useEffect(() => {
    if (!playing || times.length < 2) return;
    const step = (ts: number) => {
      if (!last.current) last.current = ts;
      const dt = ts - last.current;
      last.current = ts;
      // advance ~ real time * speed, assuming ~120 Hz samples
      const advance = (dt / 1000) * 120 * speed;
      setIndex((i) => {
        const ni = i + advance;
        if (ni >= times.length - 1) { setPlaying(false); return times.length - 1; }
        return ni;
      });
      raf.current = requestAnimationFrame(step);
    };
    raf.current = requestAnimationFrame(step);
    return () => { if (raf.current) cancelAnimationFrame(raf.current); last.current = 0; };
  }, [playing, speed, times.length]);

  const nar = props.session?._nar?.[props.lang];
  const banner = BANNER[props.lang][props.placement];
  const findings = props.session?.findings?.[props.lang];

  return (
    <div className="dash">
      {incomplete && (
        <div className="dash-warn">
          <div className="dw-title">⚠ {t("incompleteTitle")}</div>
          <div className="dw-body">{t("incompleteBody")}</div>
          {props.onGoCapture && (
            <button className="btn" onClick={props.onGoCapture}>⬆ {t("incompleteCta")}</button>
          )}
        </div>
      )}
      {banner && <div className="banner">{banner}</div>}
      {props.session?.detected_pattern && (
        <div className="pattern">{props.session.detected_pattern}</div>
      )}
      <Kpis lang={props.lang} summary={props.session?.summary || {}} />

      {times.length > 1 && series.length > 0 && (
        <div className="panel">
          <TraceChart t={times} series={series} index={Math.round(index)} />
          <div className="legend">
            {series.map((s) => (
              <span key={s.name}><i style={{ background: s.color }} /> {s.name}</span>
            ))}
          </div>
          <PlaybackControls
            lang={props.lang}
            playing={playing}
            speed={speed}
            index={Math.round(index)}
            length={times.length}
            onToggle={() => setPlaying((p) => !p)}
            onSpeed={setSpeed}
            onScrub={(i) => { setPlaying(false); setIndex(i); }}
          />
        </div>
      )}

      {/* Motion schematic, animated by the same playhead as the trace above. */}
      {times.length > 1 && (
        <MotionSchematic lang={props.lang} placement={props.placement} session={props.session} index={Math.round(index)} />
      )}

      {/* Expandable detail: per-length / per-breath / per-arm tables + symmetry. */}
      <PlacementDetails lang={props.lang} placement={props.placement} session={props.session} />

      {/* Default, rule-based analysis (no AI call) — always shown. */}
      <Findings lang={props.lang} findings={findings} />

      {/* Drills to try for this placement (verified videos + how-to). */}
      <Drills lang={props.lang} placement={props.placement} />

      {/* AI narration layers richer prose on top, on demand (paid). */}
      <div className="narrate">
        <button
          className="btn primary"
          disabled={narrating}
          onClick={async () => { setNarrating(true); try { await props.onNarrate(props.session); } finally { setNarrating(false); } }}
        >
          {narrating ? t("narrating") : `✨ ${t("narrate")}`}
        </button>
        {nar && (
          <div className="narbox">
            <div className="ailabel">{t("aiSummary")}</div>
            {nar.headline && <div className="nhead">{nar.headline}</div>}
            {nar.summary && <p className="nsum">{nar.summary}</p>}
            {Array.isArray(nar.coaching) && nar.coaching.length > 0 && (
              <ul className="coach">
                {nar.coaching.map((c: any, i: number) => (
                  <li key={i}><span className="pt">{typeof c === "string" ? c : c.point}</span></li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
