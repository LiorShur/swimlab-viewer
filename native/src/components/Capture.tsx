import { STR, type Lang } from "../lib/i18n";
import { ImportWizard } from "./ImportWizard";
import type { Recording } from "../lib/backend";

// Capture screen: the multi-DOT import wizard (one file per sensor, or trial +
// calibration), a secondary generic file import (a request.json manifest or a
// saved bundle), and the BLE connect placeholder.
export function Capture(props: {
  lang: Lang;
  busy: boolean;
  onProcess: (recordings: Recording[]) => Promise<void>;
  onFiles: (f: FileList | null) => void;
}) {
  const t = (k: string) => STR[props.lang][k] ?? k;
  return (
    <div className="screen">
      <h1 className="screen-title">{t("captureTitle")}</h1>
      <p className="screen-sub">{t("captureSub")}</p>

      <ImportWizard lang={props.lang} busy={props.busy} onProcess={props.onProcess} />

      <button className="bigcta ghost" disabled>
        <span className="bigcta-ic">📡</span>
        <span>{t("captureConnectSoon")}</span>
      </button>

      <label className="wiz-secondary">
        {t("importRec")} (JSON / CSV)
        <input type="file" accept=".csv,text/csv,application/json,.json" multiple hidden
               onChange={(e) => { props.onFiles(e.target.files); e.currentTarget.value = ""; }} />
      </label>
    </div>
  );
}
