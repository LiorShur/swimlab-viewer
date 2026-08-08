import { STR, type Lang } from "../lib/i18n";
import type { Bundle } from "../lib/backend";

// The swim session heading: date + the mathematically-derived session stats
// (pool, distance, lengths, strokes, pace, tempo), pulled from the main body
// sensor (sacrum preferred, else head). Style is front crawl — the only stroke
// the engine models today; multi-style detection is a future feature.
function sessionOf(bundle: Bundle, pid: string): any {
  const pl = bundle.placements[pid];
  if (!pl) return null;
  return pl.sessions[pl.default] ?? Object.values(pl.sessions)[0] ?? null;
}

export function SessionHeader(props: { lang: Lang; bundle: Bundle }) {
  const t = (k: string) => STR[props.lang][k] ?? k;
  const meta: any = (props.bundle as any)._meta || {};
  const sac = sessionOf(props.bundle, "sacrum");
  const head = sessionOf(props.bundle, "head");
  const main = sac || head;
  if (!main) return null;

  const s = main.summary || {};
  const pool = sac?.pool_length_m ?? meta.pool_length_m ?? 25;
  const distance = s.distance_m;
  const lengths = s.lengths;
  const strokes = s.stroke_count;
  const tempo = s.tempo_spm;

  // pace per 100 m from summed per-length active time, when available
  let pace: string | null = null;
  const lens: any[] = sac?.lengths || [];
  const totalT = lens.reduce((a, l) => a + (Number(l.duration_s) || 0), 0);
  if (distance && totalT > 0) {
    const secPer100 = (totalT / distance) * 100;
    pace = `${Math.floor(secPer100 / 60)}:${String(Math.round(secPer100 % 60)).padStart(2, "0")}`;
  }

  const dateStr = meta.date
    ? new Date(meta.date).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
    : t("shToday");
  const swimmer = meta.swimmer || main.swimmer_id;

  const tiles: { k: string; v: string | number; u?: string }[] = [
    { k: "shStyle", v: t("styleFreestyle") },
    { k: "shPool", v: pool, u: "m" },
  ];
  if (distance != null) tiles.push({ k: "shDistance", v: Math.round(distance), u: "m" });
  if (lengths != null) tiles.push({ k: "shLengths", v: lengths });
  if (strokes != null) tiles.push({ k: "shStrokes", v: strokes });
  if (pace) tiles.push({ k: "shPace", v: pace, u: "/100m" });
  if (tempo != null) tiles.push({ k: "shTempo", v: tempo, u: "spm" });

  return (
    <div className="session-head">
      <div className="sh-top">
        <span className="sh-date">{dateStr}</span>
        {swimmer && <span className="sh-swimmer">{swimmer}</span>}
      </div>
      <div className="sh-tiles">
        {tiles.map((x) => (
          <div className="sh-tile" key={x.k}>
            <div className="sh-v">{x.v}{x.u && <span className="u"> {x.u}</span>}</div>
            <div className="sh-l">{t(x.k)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
