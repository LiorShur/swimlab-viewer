import { useMemo } from "react";
import { PLACEMENT_LABEL, STR, type Lang } from "../lib/i18n";
import { Dashboard } from "./Dashboard";
import type { Bundle } from "../lib/backend";

// Home: the active swim's dashboards (placement tabs + Dashboard), or a welcome
// prompt when nothing is loaded.
export function Home(props: {
  lang: Lang;
  bundle: Bundle | null;
  active: string;
  onActive: (p: string) => void;
  onNarrate: (session: any) => Promise<void>;
  goCapture: () => void;
}) {
  const t = (k: string) => STR[props.lang][k] ?? k;
  const placements = useMemo(() => (props.bundle ? Object.keys(props.bundle.placements) : []), [props.bundle]);
  const session = useMemo(() => {
    if (!props.bundle || !props.active) return null;
    const pl = props.bundle.placements[props.active];
    return pl ? pl.sessions[pl.default] ?? Object.values(pl.sessions)[0] : null;
  }, [props.bundle, props.active]);

  if (!props.bundle || !session) {
    return (
      <div className="screen welcome">
        <div className="welcome-mark">🏊</div>
        <h1 className="screen-title">{t("homeWelcome")}</h1>
        <p className="screen-sub">{t("homeSub")}</p>
        <button className="btn primary" onClick={props.goCapture}>⬆ {t("homeImportCta")}</button>
      </div>
    );
  }

  const ICON: Record<string, string> = { head: "🏊", sacrum: "🎯", wrist: "⌚" };
  return (
    <div className="screen">
      {/* placement header/tabs — always shown so the swim is labelled, even
          with a single sensor (a single tab acts as the header). */}
      {placements.length > 0 && (
        <div className="tabs">
          {placements.map((p) => (
            <button key={p} className={"tab" + (p === props.active ? " on" : "")} onClick={() => props.onActive(p)}>
              <span className="tab-ic">{ICON[p] || "•"}</span>
              {PLACEMENT_LABEL[props.lang][p] ?? p}
            </button>
          ))}
        </div>
      )}
      <Dashboard lang={props.lang} placement={props.active} session={session} onNarrate={props.onNarrate} />
    </div>
  );
}
