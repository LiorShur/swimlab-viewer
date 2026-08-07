import { useState } from "react";
import { PLACEMENT_LABEL, PLACEMENTS, STR, type Lang } from "../lib/i18n";
import { detectPlacement, type Detection, type Recording } from "../lib/backend";

type Staged = Recording & { _single: boolean; _names: string[]; _det?: Detection | null };

const WRIST_FIRST = ["wrist_l", "wrist_r", "ankle_l", "ankle_r", "uparm_l", "uparm_r", "head", "sacrum"];
const BODY_FIRST = ["head", "sacrum", "wrist_l", "wrist_r", "ankle_l", "ankle_r", "uparm_l", "uparm_r"];

function family(pl: string): "wrist" | "body" {
  return pl.startsWith("wrist") || pl.startsWith("ankle") || pl.startsWith("uparm") ? "wrist" : "body";
}
function nextPlacement(used: Set<string>, fam: "wrist" | "body" | null): string {
  const order = fam === "wrist" ? WRIST_FIRST : fam === "body" ? BODY_FIRST : PLACEMENTS;
  return order.find((p) => !used.has(p)) ?? PLACEMENTS.find((p) => !used.has(p)) ?? "head";
}

// Capture wizard. Primary flow: select N files (one per sensor) — each becomes a
// staged sensor with an editable placement; detection runs as a wrist-vs-body
// verification hint per row, never as the router. Separate-calibration sensors
// go through the advanced form.
export function ImportWizard(props: {
  lang: Lang;
  busy: boolean;
  onProcess: (recordings: Recording[]) => Promise<void>;
}) {
  const t = (k: string) => STR[props.lang][k] ?? k;
  const [staged, setStaged] = useState<Staged[]>([]);

  // Stage one row per selected file (single-file sensors), auto-assigning a
  // distinct placement, biased by the detected family.
  async function addFiles(files: FileList | null) {
    if (!files || !files.length) return;
    const arr = [...files];
    const used = new Set(staged.map((s) => s.placement_id));
    const additions: Staged[] = [];
    for (const f of arr) {
      const text = await f.text();
      let det: Detection | null = null;
      try { det = await detectPlacement(text); } catch { /* best-effort */ }
      const pl = nextPlacement(used, det ? (det.placement === "wrist" ? "wrist" : "body") : null);
      used.add(pl);
      additions.push({ placement_id: pl, trial: text, _single: true, _names: [f.name], _det: det });
    }
    setStaged((s) => [...s, ...additions]);
  }

  function setRowPlacement(i: number, pl: string) {
    setStaged((s) => s.map((r, k) => (k === i ? { ...r, placement_id: pl } : r)));
  }
  function removeRow(i: number) {
    setStaged((s) => s.filter((_, k) => k !== i));
  }

  async function process() {
    if (!staged.length) return;
    await props.onProcess(staged.map(({ _single, _names, _det, ...r }) => r));
  }

  const usedAll = staged.map((s) => s.placement_id);
  const dup = usedAll.length !== new Set(usedAll).size;
  const anySingle = staged.some((s) => s._single);

  return (
    <div className="wizard">
      {staged.length === 0 ? (
        <div className="wiz-empty">{t("wizEmpty")}</div>
      ) : (
        <ul className="wiz-list">
          {staged.map((s, i) => {
            const detFam = s._det ? (s._det.placement === "wrist" ? "wrist" : "body") : null;
            const mism = detFam && detFam !== family(s.placement_id);
            const opts = PLACEMENTS.filter(
              (p) => p === s.placement_id || !usedAll.includes(p));
            return (
              <li key={i} className="wiz-row">
                <div className="wiz-row-main">
                  <select value={s.placement_id} onChange={(e) => setRowPlacement(i, e.target.value)}>
                    {opts.map((p) => <option key={p} value={p}>{PLACEMENT_LABEL[props.lang][p]}</option>)}
                  </select>
                  <button className="dbtn" onClick={() => removeRow(i)}>{t("wizRemove")}</button>
                </div>
                <div className="wiz-files">
                  {(s._single ? t("wizSingle") : t("wizCalset"))} · {s._names.join(", ")}
                </div>
                {s._det && (
                  <div className={"wiz-detect" + (mism ? " low" : "")}>
                    {mism
                      ? (detFam === "wrist" ? t("wizMismatchWrist") : t("wizMismatchBody"))
                      : `✓ ${t("wizConsistent")}`}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {/* primary: one file per sensor, multi-select */}
      <label className="bigcta">
        <span className="bigcta-ic">＋</span>
        <span>
          {t("wizAddFiles")}
          <span className="bigcta-hint">{t("wizAddFilesHint")}</span>
        </span>
        <input type="file" accept=".csv,text/csv" multiple hidden
               onChange={(e) => { addFiles(e.target.files); e.currentTarget.value = ""; }} />
      </label>

      <AdvancedAdd lang={props.lang} used={usedAll} onAdd={(rec) => setStaged((s) => [...s, rec])} />

      {anySingle && <div className="wiz-note">{t("wizProvisional")}</div>}
      {dup && <div className="wiz-err">{t("wizDup")}</div>}

      <button className="btn primary wiz-process"
              disabled={!staged.length || dup || props.busy} onClick={process}>
        {props.busy ? t("processing") : `${t("wizProcess")} (${staged.length})`}
      </button>
    </div>
  );
}

// Advanced: a single sensor whose calibration is two separate files.
function AdvancedAdd(props: { lang: Lang; used: string[]; onAdd: (rec: Staged) => void }) {
  const t = (k: string) => STR[props.lang][k] ?? k;
  const [open, setOpen] = useState(false);
  const options = PLACEMENTS.filter((p) => !props.used.includes(p));
  const [placement, setPlacement] = useState<string>(options[0] ?? "head");
  const [f1, setF1] = useState<File | null>(null);
  const [fa, setFa] = useState<File | null>(null);
  const [fb, setFb] = useState<File | null>(null);

  const pl = props.used.includes(placement) ? (options[0] ?? placement) : placement;
  const canAdd = !!f1 && !!fa && !!fb && !props.used.includes(pl);

  async function add() {
    if (!f1 || !fa || !fb) return;
    props.onAdd({
      placement_id: pl, trial: await f1.text(), t0a: await fa.text(), t0b: await fb.text(),
      _single: false, _names: [f1.name, fa.name, fb.name], _det: null,
    });
    setF1(null); setFa(null); setFb(null);
  }

  return (
    <div className="wiz-adv">
      <button className="wiz-adv-toggle" onClick={() => setOpen((o) => !o)}>
        {open ? "▾" : "▸"} {t("wizAdvanced")}
      </button>
      {open && (
        <div className="wiz-add">
          <label className="wiz-field">
            <span>{t("wizPlacement")}</span>
            <select value={pl} onChange={(e) => setPlacement(e.target.value)}>
              {options.map((p) => <option key={p} value={p}>{PLACEMENT_LABEL[props.lang][p]}</option>)}
            </select>
          </label>
          <FilePick label={t("wizTrial")} file={f1} onPick={setF1} pick={t("wizPick")} />
          <FilePick label={t("wizT0a")} file={fa} onPick={setFa} pick={t("wizPick")} />
          <FilePick label={t("wizT0b")} file={fb} onPick={setFb} pick={t("wizPick")} />
          <button className="btn" disabled={!canAdd} onClick={add}>＋ {t("wizAdvancedAdd")}</button>
        </div>
      )}
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
