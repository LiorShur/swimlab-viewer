import { STR, type Lang } from "../lib/i18n";

const SPEEDS = [0.5, 1, 2, 4] as const;

export function PlaybackControls(props: {
  lang: Lang;
  playing: boolean;
  speed: number;
  index: number;
  length: number;
  onToggle: () => void;
  onSpeed: (s: number) => void;
  onScrub: (i: number) => void;
}) {
  const t = (k: string) => STR[props.lang][k] ?? k;
  return (
    <div className="playback">
      <button className="btn" onClick={props.onToggle}>
        {props.playing ? `⏸ ${t("pause")}` : `▶ ${t("play")}`}
      </button>
      <label className="speed">
        {t("speed")}
        <select value={props.speed} onChange={(e) => props.onSpeed(Number(e.target.value))}>
          {SPEEDS.map((s) => (
            <option key={s} value={s}>{s}×</option>
          ))}
        </select>
      </label>
      <input
        className="scrub"
        type="range"
        min={0}
        max={Math.max(0, props.length - 1)}
        value={props.index}
        onChange={(e) => props.onScrub(Number(e.target.value))}
      />
    </div>
  );
}
