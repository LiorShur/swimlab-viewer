import { useState } from "react";
import { STR, type Lang } from "../lib/i18n";

// First-run intro (3 slides), shown once. Skippable. The choice is persisted by
// the caller (localStorage) so it never blocks returning users.
export function Onboarding(props: { lang: Lang; onDone: () => void }) {
  const t = (k: string) => STR[props.lang][k] ?? k;
  const slides = [
    { icon: "🏊", title: t("ob1t"), body: t("ob1b") },
    { icon: "🎯", title: t("ob2t"), body: t("ob2b") },
    { icon: "✨", title: t("ob3t"), body: t("ob3b") },
  ];
  const [i, setI] = useState(0);
  const last = i === slides.length - 1;
  return (
    <div className="onboarding">
      <button className="ob-skip" onClick={props.onDone}>{t("obSkip")}</button>
      <div className="ob-slide">
        <div className="ob-icon">{slides[i].icon}</div>
        <div className="ob-title">{slides[i].title}</div>
        <p className="ob-body">{slides[i].body}</p>
      </div>
      <div className="ob-dots">
        {slides.map((_, k) => <span key={k} className={"dot" + (k === i ? " on" : "")} />)}
      </div>
      <button className="btn primary ob-next" onClick={() => (last ? props.onDone() : setI(i + 1))}>
        {last ? t("obStart") : t("obNext")}
      </button>
    </div>
  );
}
