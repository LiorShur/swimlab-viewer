import { STR, type Lang } from "../lib/i18n";

// Capture screen: import recordings today; live BLE sensor capture lands here
// later. The multi-DOT import wizard will replace the simple picker below.
export function Capture(props: { lang: Lang; busy: boolean; onFiles: (f: FileList | null) => void }) {
  const t = (k: string) => STR[props.lang][k] ?? k;
  return (
    <div className="screen">
      <h1 className="screen-title">{t("captureTitle")}</h1>
      <p className="screen-sub">{t("captureSub")}</p>

      <label className="bigcta">
        <span className="bigcta-ic">⬆</span>
        <span>{props.busy ? t("processing") : t("importRec")}</span>
        <input type="file" accept=".csv,text/csv,application/json,.json" multiple hidden
               onChange={(e) => { props.onFiles(e.target.files); e.currentTarget.value = ""; }} />
      </label>

      <button className="bigcta ghost" disabled>
        <span className="bigcta-ic">📡</span>
        <span>{t("captureConnectSoon")}</span>
      </button>
    </div>
  );
}
