import { useEffect, useMemo, useRef, useState } from "react";
import { STR, type Lang } from "../lib/i18n";
import { PlaybackControls } from "./PlaybackControls";
import { TraceChart, type Series } from "./TraceChart";

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

function Kpis(props: { summary: Record<string, any> }) {
  const entries = Object.entries(props.summary || {}).filter(
    ([, v]) => typeof v === "number" && Number.isFinite(v),
  );
  if (!entries.length) return null;
  return (
    <div className="kpis">
      {entries.slice(0, 8).map(([k, v]) => (
        <div className="kpi" key={k}>
          <div className="k-lab">{k.replace(/_/g, " ")}</div>
          <div className="k-val">{Number(v).toFixed(2)}</div>
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
}) {
  const t = (k: string) => STR[props.lang][k] ?? k;
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

  return (
    <div className="dash">
      {props.session?.detected_pattern && (
        <div className="pattern">{props.session.detected_pattern}</div>
      )}
      <Kpis summary={props.session?.summary || {}} />

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
            {nar.headline && <div className="nhead">{nar.headline}</div>}
            {nar.summary && <p className="nsum">{nar.summary}</p>}
          </div>
        )}
      </div>
    </div>
  );
}
