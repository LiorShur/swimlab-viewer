import { useEffect, useState } from "react";
import { getRedirectResult, onAuthStateChanged, signOut, type User } from "firebase/auth";
import { auth } from "./lib/firebase";
import { STR, dirFor, type Lang } from "./lib/i18n";
import { AuthGate } from "./components/AuthGate";
import { Splash } from "./components/Splash";
import { Onboarding } from "./components/Onboarding";
import { BottomNav, type Tab } from "./components/BottomNav";
import { Home } from "./components/Home";
import { Capture } from "./components/Capture";
import { History } from "./components/History";
import { Settings } from "./components/Settings";
import { filesToRecordings } from "./ble/dot";
import { isUpgradeRequired, narrate, processSession, type Bundle, type Recording } from "./lib/backend";

const newSwimId = () => `swim-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
const ONBOARDED = "swimlab.onboarded";

export default function App() {
  const [lang, setLang] = useState<Lang>((localStorage.getItem("swimlab.lang") as Lang) || "he");
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [showSplash, setShowSplash] = useState(true);
  const [onboarded, setOnboarded] = useState(!!localStorage.getItem(ONBOARDED));
  const [tab, setTab] = useState<Tab>("home");
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [active, setActive] = useState<string>("");
  const [busy, setBusy] = useState(false);

  const t = (k: string) => STR[lang][k] ?? k;

  useEffect(() => onAuthStateChanged(auth, (u) => { setUser(u); setReady(true); }), []);
  useEffect(() => { getRedirectResult(auth).catch(() => {}); }, []);  // complete a mobile redirect sign-in
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = dirFor(lang);
    localStorage.setItem("swimlab.lang", lang);
  }, [lang]);

  function openBundle(b: Bundle) {
    if (!(b as any)._meta) (b as any)._meta = { date: new Date().toISOString() };  // fresh swim = now
    const order = ["head", "sacrum", "wrist", "ankle_l", "ankle_r", "uparm_l", "uparm_r"];
    const present = Object.keys(b.placements);
    setBundle(b);
    setActive(order.find((p) => present.includes(p)) || present[0] || "");
    setTab("home");
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
        openBundle(await processSession(recordings, { swimId: user ? newSwimId() : undefined }));
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

  async function processRecordings(recordings: Recording[]) {
    setBusy(true);
    try {
      openBundle(await processSession(recordings, { swimId: user ? newSwimId() : undefined }));
    } catch (e: any) {
      alert("Processing failed: " + (e?.message || e));
    } finally { setBusy(false); }
  }

  async function onNarrate(sess: any) {
    try {
      const res = await narrate(sess, sess.placement || active);
      sess._nar = res.narratives;
      setBundle((b) => (b ? { ...b } : b));
    } catch (e: any) {
      alert(isUpgradeRequired(e) ? t("upgrade") : "Narration failed: " + (e?.message || e));
    }
  }

  if (showSplash) return <Splash lang={lang} onDone={() => setShowSplash(false)} />;
  if (!onboarded) return <Onboarding lang={lang} onDone={() => { localStorage.setItem(ONBOARDED, "1"); setOnboarded(true); }} />;
  if (!ready) return <div className="loading">…</div>;
  if (!user) return <AuthGate lang={lang} />;

  return (
    <div className="app">
      <header className="brandbar">
        <span className="brand">swimlab</span>
      </header>

      <div className="screenwrap">
        {tab === "home" && (
          <Home lang={lang} bundle={bundle} active={active} onActive={setActive}
                onNarrate={onNarrate} goCapture={() => setTab("capture")} />
        )}
        {tab === "capture" && <Capture lang={lang} busy={busy} onProcess={processRecordings} onFiles={handleFiles} />}
        {tab === "history" && <History lang={lang} onOpen={openBundle} />}
        {tab === "settings" && (
          <Settings lang={lang} user={user} tier="free"
                    onToggleLang={() => setLang(lang === "he" ? "en" : "he")}
                    onSignOut={() => signOut(auth)} />
        )}
      </div>

      <BottomNav lang={lang} tab={tab} onTab={setTab} />
    </div>
  );
}
