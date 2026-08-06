import { useEffect, useState } from "react";
import { listSwims, loadBundle, type Bundle, type SwimDoc } from "../lib/backend";
import { STR, type Lang } from "../lib/i18n";

// The signed-in user's saved swims. Clicking one loads its bundle from Storage.
export function History(props: { lang: Lang; onOpen: (b: Bundle) => void }) {
  const t = (k: string) => STR[props.lang][k] ?? k;
  const [swims, setSwims] = useState<SwimDoc[] | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { listSwims().then(setSwims).catch(() => setSwims([])); }, []);

  const when = (ts: SwimDoc["createdAt"]) => {
    try {
      const d = ts && typeof ts === "object" && "seconds" in ts ? new Date(ts.seconds * 1000)
        : ts ? new Date(ts as string) : null;
      return d ? d.toLocaleString() : "";
    } catch { return ""; }
  };

  if (swims === null) return <div className="hist muted">…</div>;
  if (!swims.length) return <div className="hist muted">{t("noSwims")}</div>;

  return (
    <ul className="hist">
      {swims.map((s) => (
        <li key={s.id} onClick={async () => {
          if (!s.bundlePath || busy) return;
          setBusy(true);
          try { props.onOpen(await loadBundle(s.bundlePath)); } finally { setBusy(false); }
        }}>
          <div>
            <div className="hname">{s.swimmer_id || s.id}</div>
            <div className="hsub">{when(s.createdAt)}</div>
          </div>
          <div className="hpl">{(s.summary?.placements || []).join(" · ")}</div>
        </li>
      ))}
    </ul>
  );
}
