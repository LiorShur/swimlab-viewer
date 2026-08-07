import type { User } from "firebase/auth";
import { STR, type Lang } from "../lib/i18n";

// Settings: account, plan, language, about. (Tier display/upgrade wires to the
// entitlement in a later pass; free is the default.)
export function Settings(props: {
  lang: Lang;
  user: User | null;
  tier: string;
  onToggleLang: () => void;
  onSignOut: () => void;
}) {
  const t = (k: string) => STR[props.lang][k] ?? k;
  return (
    <div className="screen">
      <h1 className="screen-title">{t("settingsTitle")}</h1>

      <div className="setgroup">
        <div className="setrow"><span>{t("settAccount")}</span><span className="setval">{props.user?.email || props.user?.displayName || "—"}</span></div>
        <div className="setrow"><span>{t("settTier")}</span><span className="setval">{props.tier === "paid" ? t("tierPaid") : t("tierFree")}</span></div>
        <div className="setrow"><span>{t("settLanguage")}</span>
          <button className="btn" onClick={props.onToggleLang}>🌐 {t("langToggle")}</button>
        </div>
      </div>

      <div className="setgroup">
        <div className="setrow"><span>{t("settAbout")}</span></div>
        <p className="screen-sub">{t("aboutText")}</p>
      </div>

      <button className="btn danger" onClick={props.onSignOut}>⎋ {t("signOut")}</button>
    </div>
  );
}
