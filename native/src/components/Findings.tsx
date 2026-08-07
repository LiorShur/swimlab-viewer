import { STR, type Lang } from "../lib/i18n";

export type FindingSet = {
  headline?: string;
  summary?: string;
  coaching?: { point: string; metric?: string }[];
};

// Default, rule-based analysis (no AI call) — the bilingual findings the backend
// already attaches to every session payload. Mirrors the web app's summary ->
// coaching layout.
export function Findings(props: { lang: Lang; findings?: FindingSet }) {
  const t = (k: string) => STR[props.lang][k] ?? k;
  const f = props.findings;
  if (!f || (!f.headline && !f.summary && !(f.coaching && f.coaching.length))) return null;
  return (
    <div className="findings">
      {f.headline && <div className="fhead">{f.headline}</div>}
      {f.summary && <p className="fsum">{f.summary}</p>}
      {f.coaching && f.coaching.length > 0 && (
        <>
          <div className="clabel">{t("coaching")}</div>
          <ul className="coach">
            {f.coaching.map((c, i) => (
              <li key={i}>
                <span className="pt">{c.point}</span>
                {c.metric && <span className="mchip">{c.metric}</span>}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
