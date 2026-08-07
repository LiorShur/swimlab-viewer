import { useEffect, useState } from "react";
import { STR, type Lang } from "../lib/i18n";

// Brief branded splash on launch, then fades out. (On device, the Capacitor
// SplashScreen plugin covers the cold-start; this covers the web/app warm start.)
export function Splash(props: { lang: Lang; onDone: () => void }) {
  const [leaving, setLeaving] = useState(false);
  useEffect(() => {
    const a = setTimeout(() => setLeaving(true), 1100);
    const b = setTimeout(props.onDone, 1500);
    return () => { clearTimeout(a); clearTimeout(b); };
  }, [props.onDone]);
  return (
    <div className={"splash" + (leaving ? " leaving" : "")}>
      <div className="splash-mark">🏊</div>
      <div className="splash-name">swimlab</div>
      <div className="splash-tag">{STR[props.lang].tagline}</div>
    </div>
  );
}
