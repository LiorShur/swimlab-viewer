import { useState } from "react";
import { DRILLS, type Drill } from "../lib/drills";
import { STR, type Lang } from "../lib/i18n";

// Drills library for a placement: each drill has a Watch button (opens a
// YouTube modal) and a How-to toggle. Mirrors the web app's drills panel.
export function Drills(props: { lang: Lang; placement: string }) {
  const t = (k: string) => STR[props.lang][k] ?? k;
  const lib: Drill[] = DRILLS[props.placement] || [];
  const [open, setOpen] = useState<Record<number, boolean>>({});
  const [video, setVideo] = useState<Drill | null>(null);

  if (!lib.length) return null;

  return (
    <div className="panel">
      <h2>{t("drillsLib")}</h2>
      <ul className="drills">
        {lib.map((d, i) => (
          <li key={i}>
            <div className="dname">{d.name[props.lang] || d.name.en}</div>
            <div className="dacts">
              <button className="dbtn" onClick={() => setVideo(d)}>{t("drillWatch")}</button>
              <button className="dbtn" onClick={() => setOpen((o) => ({ ...o, [i]: !o[i] }))}>{t("drillHowto")}</button>
            </div>
            {open[i] && <div className="dhowto">{d.howto[props.lang] || d.howto.en}</div>}
          </li>
        ))}
      </ul>

      {video && (
        <div className="vmodal" onClick={(e) => { if (e.target === e.currentTarget) setVideo(null); }}>
          <div className="vbox" role="dialog" aria-modal="true">
            <div className="vbar">
              <span>{video.name[props.lang] || video.name.en}</span>
              <button className="vclose" aria-label={t("drillClose")} onClick={() => setVideo(null)}>✕</button>
            </div>
            <div className="vframe">
              <iframe
                src={`https://www.youtube.com/embed/${video.yt}?rel=0&playsinline=1&autoplay=1`}
                title={video.name.en}
                allow="autoplay; encrypted-media; fullscreen"
                allowFullScreen
              />
            </div>
            <a className="vopen" href={`https://www.youtube.com/watch?v=${video.yt}`} target="_blank" rel="noopener">
              {t("drillOpenYt")}
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
