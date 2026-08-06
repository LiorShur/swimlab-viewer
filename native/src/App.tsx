import { useEffect, useMemo, useState } from "react";
import { onAuthStateChanged, signOut, type User } from "firebase/auth";
import { auth } from "./lib/firebase";
import { STR, dirFor, type Lang } from "./lib/i18n";
import { AuthGate } from "./components/AuthGate";
import { Dashboard } from "./components/Dashboard";
import { History } from "./components/History";
import { filesToRecordings } from "./ble/dot";
import { isUpgradeRequired, narrate, processSession, type Bundle } from "./lib/backend";

const newSwimId = () => `swim-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

export default function App() {
  const [lang, setLang] = useState<Lang>("he");
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [active, setActive] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const t = (k: string) => STR[lang][k] ?? k;

  useEffect(() => onAuthStateChanged(auth, (u) => { setUser(u); setReady(true); }), []);
  useEffect(() => { document.documentElement.lang = lang; document.documentElement.dir = dirFor(lang); }, [lang]);

  const placements = useMemo(() => (bundle ? Object.keys(bundle.placements) : []), [bundle]);
  const session = useMemo(() => {
    if (!bundle || !active) return null;
    const pl = bundle.placements[active];
    return pl ? pl.sessions[pl.default] ?? Object.values(pl.sessions)[0] : null;
  }, [bundle, active]);

  function openBundle(b: Bundle) {
    setBundle(b);
    setActive(b.default_placement && b.placements[b.default_placement] ? b.default_placement : Object.keys(b.placements)[0] || "");
    setShowHistory(false);
  }

  async function handleFiles(files: FileList | null) {
    if (!files || !files.length) return;
    const arr = [...files];
    const csvs = arr.filter((f) => /\.csv$/i.test(f.name) || f.type === "text/csv");
    setBusy(true);
    try {
      if (csvs.length) {
        const { recordings, unmatched } = await filesToRecordings(csvs);
        if (!recordings.length) { alert("Couldn't match placement/pose in the CSV names.\n" + unmatched.join(", ")); return; }
        const b = await processSession(recordings, { swimId: user ? newSwimId() : undefined });
        openBundle(b);
      } else {
        const obj = JSON.parse(await arr[0].text());
        if (obj.recordings || obj.data?.recordings) {
          const recs = obj.recordings || obj.data.recordings;
          const pool = obj.pool_length_m || obj.data?.pool_length_m || 25;
          openBundle(await processSession(recs, { poolLengthM: pool, swimId: user ? newSwimId() : undefined }));
        } else if (obj.placements) {
          openBundle(obj as Bundle);
        } else { alert("Unrecognised file."); }
      }
    } catch (e: any) {
      alert("Processing failed: " + (e?.message || e));
    } finally { setBusy(false); }
  }

  async function onNarrate(sess: any) {
    try {
      const res = await narrate(sess, sess.placement || active);
      sess._nar = res.narratives;
      setBundle((b) => (b ? { ...b } : b)); // force re-render
    } catch (e: any) {
      alert(isUpgradeRequired(e) ? t("upgrade") : "Narration failed: " + (e?.message || e));
    }
  }

  if (!ready) return <div className="loading">…</div>;
  if (!user) return <AuthGate lang={lang} />;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">swimlab <span className="tag">· {t("tagline")}</span></div>
        <div className="tools">
          <button className="btn" onClick={() => setLang(lang === "he" ? "en" : "he")}>🌐 {t("langToggle")}</button>
          <label className="btn">
            {busy ? t("processing") : `⬆ ${t("importRec")}`}
            <input type="file" accept=".csv,text/csv,application/json,.json" multiple hidden
                   onChange={(e) => { handleFiles(e.target.files); e.currentTarget.value = ""; }} />
          </label>
          <button className="btn" onClick={() => setShowHistory((s) => !s)}>⌛ {t("history")}</button>
          <button className="btn" onClick={() => signOut(auth)} title={user.email || ""}>⎋ {t("signOut")}</button>
        </div>
      </header>

      {showHistory && <History lang={lang} onOpen={openBundle} />}

      {placements.length > 0 && (
        <div className="tabs">
          {placements.map((p) => (
            <button key={p} className={"tab" + (p === active ? " on" : "")} onClick={() => setActive(p)}>{p}</button>
          ))}
        </div>
      )}

      {session ? (
        <Dashboard lang={lang} placement={active} session={session} onNarrate={onNarrate} />
      ) : (
        <div className="empty">{t("importRec")} · {t("connectSensor")}</div>
      )}
    </div>
  );
}
