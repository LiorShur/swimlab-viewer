import { useEffect, useMemo, useState } from "react";
import { getSwim, listSwims, type Bundle, type SwimDoc } from "../lib/backend";
import { STR, type Lang } from "../lib/i18n";

const secs = (ts: SwimDoc["createdAt"]): number | null => {
  if (!ts) return null;
  if (typeof ts === "object" && "seconds" in ts) return ts.seconds;
  const d = Date.parse(ts as string);
  return Number.isNaN(d) ? null : d / 1000;
};

// Saved swims + accumulated stats. Opening a swim goes through the backend
// (get_swim) so the Storage read is server-side (no browser CORS).
export function History(props: { lang: Lang; onOpen: (b: Bundle) => void }) {
  const t = (k: string) => STR[props.lang][k] ?? k;
  const [swims, setSwims] = useState<SwimDoc[] | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { listSwims().then(setSwims).catch(() => setSwims([])); }, []);

  const stats = useMemo(() => {
    if (!swims || !swims.length) return null;
    let dist = 0, lengths = 0, earliest = Infinity;
    for (const s of swims) {
      const per = s.summary?.per_placement || {};
      const sac: any = per.sacrum || {};
      dist += Number(sac.distance_m || 0);
      lengths += Number(sac.lengths || 0);
      const sc = secs(s.createdAt);
      if (sc != null) earliest = Math.min(earliest, sc);
    }
    return { count: swims.length, dist: Math.round(dist), lengths,
             since: Number.isFinite(earliest) ? new Date(earliest * 1000) : null };
  }, [swims]);

  const when = (ts: SwimDoc["createdAt"]) => {
    const sc = secs(ts);
    return sc == null ? "" : new Date(sc * 1000).toLocaleDateString();
  };

  async function open(s: SwimDoc) {
    if (busy) return;
    setBusy(true);
    try {
      const bundle = await getSwim(s.id);
      (bundle as any)._meta = { date: secs(s.createdAt) ? new Date(secs(s.createdAt)! * 1000).toISOString() : null,
                                swimmer: s.swimmer_id, pool_length_m: s.pool_length_m };
      props.onOpen(bundle);
    } catch (e: any) {
      alert(t("histOpenFail") + " " + (e?.message || ""));
    } finally { setBusy(false); }
  }

  return (
    <div className="screen">
      <h1 className="screen-title">{t("histScreenTitle")}</h1>

      {stats && (
        <div className="hist-stats">
          <div className="hstat"><div className="hstat-v">{stats.count}</div><div className="hstat-l">{t("statSwims")}</div></div>
          <div className="hstat"><div className="hstat-v">{stats.dist}<span className="u"> m</span></div><div className="hstat-l">{t("statDistance")}</div></div>
          <div className="hstat"><div className="hstat-v">{stats.lengths}</div><div className="hstat-l">{t("statLengths")}</div></div>
          {stats.since && <div className="hstat"><div className="hstat-v sm">{stats.since.toLocaleDateString()}</div><div className="hstat-l">{t("statSince")}</div></div>}
        </div>
      )}

      {swims === null ? (
        <div className="muted">…</div>
      ) : !swims.length ? (
        <div className="muted">{t("noSwims")}</div>
      ) : (
        <ul className="hist">
          {swims.map((s) => (
            <li key={s.id} onClick={() => open(s)}>
              <div>
                <div className="hname">{s.swimmer_id || s.id}</div>
                <div className="hsub">{when(s.createdAt)}</div>
              </div>
              <div className="hpl">{(s.summary?.placements || []).join(" · ")}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
