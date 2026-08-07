import { STR, type Lang } from "../lib/i18n";

export type Tab = "home" | "capture" | "history" | "settings";

const TABS: { id: Tab; icon: string; key: string }[] = [
  { id: "home", icon: "🏠", key: "navHome" },
  { id: "capture", icon: "⬆", key: "navCapture" },
  { id: "history", icon: "⌛", key: "navHistory" },
  { id: "settings", icon: "⚙", key: "navSettings" },
];

export function BottomNav(props: { lang: Lang; tab: Tab; onTab: (t: Tab) => void }) {
  const t = (k: string) => STR[props.lang][k] ?? k;
  return (
    <nav className="bottomnav">
      {TABS.map((x) => (
        <button key={x.id} className={"navbtn" + (x.id === props.tab ? " on" : "")} onClick={() => props.onTab(x.id)}>
          <span className="navic">{x.icon}</span>
          <span className="navlab">{t(x.key)}</span>
        </button>
      ))}
    </nav>
  );
}
