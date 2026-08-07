import { useState } from "react";
import { PLACEMENTS, PLACEMENT_LABEL, STR, type Lang } from "../lib/i18n";
import type { Recording } from "../lib/backend";

type Mode = "single" | "calset";
type Staged = Recording & { _single: boolean; _names: string[] };

// Multi-DOT capture wizard: add one sensor at a time (single file, or trial +
// two calibration files), review the staged list, then process the session.
export function ImportWizard(props: {
  lang: Lang;
  busy: boolean;
  onProcess: (recordings: Recording[]) => Promise<void>;
}) {
  const t = (k: string) => STR[props.lang][k] ?? k;
  const [staged, setStaged] = useState<Staged[]>([]);
  const [placement, setPlacement] = useState<string>(PLACEMENTS[0]);
  const [mode, setMode] = useState<Mode>("single");
  const [f1, setF1] = useState<File | null>(null); // swim / single
  const [fa, setFa] = useState<File | null>(null); // T0a
  const [fb, setFb] = useState<File | null>(null); // T0b
  const [err, setErr] = useState<string | null>(null);

  const used = new Set(staged.map((s) => s.placement_id));
  const options = PLACEMENTS.filter((p) => !used.has(p) || p === placement);
  const canAdd = !!f1 && (mode === "single" || (!!fa && !!fb)) && !used.has(placement);

  async function add() {
    setErr(null);
    if (used.has(placement)) { setErr(t("wizDup")); return; }
    if (!f1) return;
    const rec: Staged = {
      placement_id: placement,
      trial: await f1.text(),
      _single: mode === "single",
      _names: [f1.name],
    };
    if (mode === "calset" && fa && fb) {
      rec.t0a = await fa.text(); rec.t0b = await fb.text();
      rec._names.push(fa.name, fb.name);
    }
    setStaged((s) => [...s, rec]);
    setF1(null); setFa(null); setFb(null);
    const next = PLACEMENTS.find((p) => !used.has(p) && p !== placement);
    if (next) setPlacement(next);
  }

  async function process() {
    if (!staged.length) return;
    const recordings: Recording[] = staged.map(({ _single, _names, ...r }) => r);
    await props.onProcess(recordings);
  }

  const anySingle = staged.some((s) => s._single);

  return (
    <div className="wizard">
      {/* staged sensors */}
      {staged.length === 0 ? (
        <div className="wiz-empty">{t("wizEmpty")}</div>
      ) : (
        <ul className="wiz-list">
          {staged.map((s, i) => (
            <li key={s.placement_id}>
              <div>
                <div className="wiz-pl">{PLACEMENT_LABEL[props.lang][s.placement_id]}</div>
                <div className="wiz-files">{s._single ? t("wizSingle") : t("wizCalset")} · {s._names.join(", ")}</div>
              </div>
              <button className="dbtn" onClick={() => setStaged((x) => x.filter((_, k) => k !== i))}>{t("wizRemove")}</button>
            </li>
          ))}
        </ul>
      )}

      {/* add-a-sensor form */}
      <div className="wiz-add">
        <div className="wiz-add-title">{t("wizAddSensor")}</div>
        <label className="wiz-field">
          <span>{t("wizPlacement")}</span>
          <select value={placement} onChange={(e) => setPlacement(e.target.value)}>
            {options.map((p) => <option key={p} value={p}>{PLACEMENT_LABEL[props.lang][p]}</option>)}
          </select>
        </label>
        <label className="wiz-field">
          <span>{t("wizFiles")}</span>
          <select value={mode} onChange={(e) => setMode(e.target.value as Mode)}>
            <option value="single">{t("wizSingle")}</option>
            <option value="calset">{t("wizCalset")}</option>
          </select>
        </label>

        <FilePick label={mode === "single" ? t("wizTrial") : t("wizTrial")} file={f1} onPick={setF1} pick={t("wizPick")} />
        {mode === "calset" && <FilePick label={t("wizT0a")} file={fa} onPick={setFa} pick={t("wizPick")} />}
        {mode === "calset" && <FilePick label={t("wizT0b")} file={fb} onPick={setFb} pick={t("wizPick")} />}

        {err && <div className="wiz-err">{err}</div>}
        <button className="btn" disabled={!canAdd} onClick={add}>＋ {t("wizAddBtn")}</button>
      </div>

      {anySingle && <div className="wiz-note">{t("wizProvisional")}</div>}

      <button className="btn primary wiz-process" disabled={!staged.length || props.busy} onClick={process}>
        {props.busy ? t("processing") : `${t("wizProcess")} (${staged.length})`}
      </button>
    </div>
  );
}

function FilePick(props: { label: string; file: File | null; onPick: (f: File | null) => void; pick: string }) {
  return (
    <label className="wiz-file">
      <span className="wiz-file-lab">{props.label}</span>
      <span className="wiz-file-btn">{props.file ? props.file.name : props.pick}</span>
      <input type="file" accept=".csv,text/csv" hidden
             onChange={(e) => props.onPick(e.target.files?.[0] || null)} />
    </label>
  );
}
