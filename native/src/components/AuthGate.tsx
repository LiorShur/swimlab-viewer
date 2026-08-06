import { useState } from "react";
import {
  GoogleAuthProvider, createUserWithEmailAndPassword,
  signInWithEmailAndPassword, signInWithPopup,
} from "firebase/auth";
import { auth } from "../lib/firebase";
import { STR, type Lang } from "../lib/i18n";

// Sign-in screen (Google + Email/Password). Shown until a user is present.
export function AuthGate(props: { lang: Lang }) {
  const t = (k: string) => STR[props.lang][k] ?? k;
  const [mode, setMode] = useState<"signin" | "register">("signin");
  const [email, setEmail] = useState("");
  const [pass, setPass] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const google = async () => {
    setErr(null);
    try { await signInWithPopup(auth, new GoogleAuthProvider()); }
    catch (e: any) { setErr(e?.message || String(e)); }
  };
  const submit = async () => {
    setErr(null);
    if (!email || !pass) { setErr(t("email") + " + " + t("password")); return; }
    try {
      if (mode === "register") await createUserWithEmailAndPassword(auth, email, pass);
      else await signInWithEmailAndPassword(auth, email, pass);
    } catch (e: any) { setErr(e?.message || String(e)); }
  };

  return (
    <div className="authgate">
      <div className="authcard">
        <h1>swimlab</h1>
        <p className="tag">{t("tagline")}</p>
        <button className="btn gbtn" onClick={google}><b>G</b> {t("google")}</button>
        <div className="or"><span>{t("or")}</span></div>
        <input className="inp" type="email" placeholder={t("email")} value={email} onChange={(e) => setEmail(e.target.value)} />
        <input className="inp" type="password" placeholder={t("password")} value={pass} onChange={(e) => setPass(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} />
        {err && <div className="err">{err}</div>}
        <button className="btn primary" onClick={submit}>{mode === "register" ? t("createAccount") : t("signIn")}</button>
        <a className="link" onClick={() => setMode(mode === "register" ? "signin" : "register")}>
          {mode === "register" ? t("haveAccount") : t("needAccount")}
        </a>
      </div>
    </div>
  );
}
