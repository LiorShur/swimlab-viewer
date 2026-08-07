import { useEffect, useMemo, useRef } from "react";
import { MOTION_HINT, MOTION_TITLE, type Lang } from "../lib/i18n";

// Motion schematic driven by the recorded traces, ported from the web app
// (drawHead / drawBody / drawArms). It shares the Dashboard's playhead `index`,
// so play/pause/speed/scrub animate the trace and the figure together.
const cssv = (n: string) =>
  getComputedStyle(document.documentElement).getPropertyValue(n).trim() || "";

function drawHead(ctx: CanvasRenderingContext2D, W: number, H: number, pitch: number, roll: number) {
  const accent = cssv("--accent"), muted = cssv("--muted"), left = cssv("--left");
  const cx = W * 0.3, cy = H * 0.46;
  ctx.save(); ctx.translate(cx, cy); ctx.rotate((roll * Math.PI) / 180);
  ctx.strokeStyle = accent; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.arc(0, 0, 32, 0, 2 * Math.PI); ctx.stroke();
  ctx.beginPath(); ctx.arc(-32, 0, 5, 0, 2 * Math.PI); ctx.arc(32, 0, 5, 0, 2 * Math.PI); ctx.stroke();
  ctx.fillStyle = accent; ctx.beginPath(); ctx.arc(0, 24, 4, 0, 2 * Math.PI); ctx.fill();
  ctx.restore();
  ctx.fillStyle = muted; ctx.font = "11px " + cssv("--mono"); ctx.textAlign = "center"; ctx.textBaseline = "alphabetic";
  ctx.fillText("roll " + (roll >= 0 ? "+" : "") + roll.toFixed(0) + "°", cx, H - 8);
  const cx2 = W * 0.7;
  ctx.save(); ctx.translate(cx2, cy); ctx.rotate((-pitch * Math.PI) / 180);
  ctx.strokeStyle = left; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.arc(0, 0, 28, 0, 2 * Math.PI); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(26, 0); ctx.lineTo(42, 0); ctx.stroke();
  ctx.restore();
  ctx.fillStyle = muted; ctx.fillText("pitch " + (pitch >= 0 ? "+" : "") + pitch.toFixed(0) + "°", cx2, H - 8);
}

function drawBody(ctx: CanvasRenderingContext2D, W: number, H: number, roll: number) {
  const accent = cssv("--accent"), muted = cssv("--muted");
  const cx = W * 0.5, hipY = H * 0.76;
  ctx.save(); ctx.translate(cx, hipY); ctx.rotate((roll * Math.PI) / 180);
  ctx.strokeStyle = accent; ctx.lineWidth = 3; ctx.lineCap = "round";
  ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, -66); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(-32, -58); ctx.lineTo(32, -58); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(-22, 2); ctx.lineTo(22, 2); ctx.stroke();
  ctx.beginPath(); ctx.arc(0, -82, 13, 0, 2 * Math.PI); ctx.stroke();
  ctx.restore();
  ctx.fillStyle = muted; ctx.font = "11px " + cssv("--mono"); ctx.textAlign = "center"; ctx.textBaseline = "alphabetic";
  ctx.fillText("body roll " + (roll >= 0 ? "+" : "") + roll.toFixed(0) + "°", cx, H - 6);
}

function drawArms(ctx: CanvasRenderingContext2D, W: number, H: number, pR: number, pL: number) {
  const right = cssv("--right") || cssv("--accent"), left = cssv("--left"), muted = cssv("--muted"), line = cssv("--line");
  const cy = H * 0.4, sx = W * 0.5, sw = 64, armLen = 62;
  ctx.strokeStyle = line; ctx.lineWidth = 3; ctx.lineCap = "round";
  ctx.beginPath(); ctx.moveTo(sx - sw, cy); ctx.lineTo(sx + sw, cy); ctx.stroke();
  ctx.beginPath(); ctx.arc(sx, cy - 15, 10, 0, 2 * Math.PI); ctx.stroke();
  const arm = (shX: number, pitch: number, color: string, dir: number) => {
    ctx.save(); ctx.translate(shX, cy); ctx.rotate((-pitch * Math.PI) / 180);
    ctx.strokeStyle = color; ctx.lineWidth = 4;
    ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(dir * 8, armLen); ctx.stroke();
    ctx.fillStyle = color; ctx.beginPath(); ctx.arc(dir * 8, armLen, 5, 0, 2 * Math.PI); ctx.fill();
    ctx.restore();
  };
  arm(sx + sw, pR, right, 1); arm(sx - sw, pL, left, -1);
  ctx.fillStyle = muted; ctx.font = "11px " + cssv("--mono"); ctx.textAlign = "center"; ctx.textBaseline = "alphabetic";
  ctx.fillText("R " + (pR >= 0 ? "+" : "") + pR.toFixed(0) + "°    L " + (pL >= 0 ? "+" : "") + pL.toFixed(0) + "°", sx, H - 6);
}

export function MotionSchematic(props: { lang: Lang; placement: string; session: any; index: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const arrays = useMemo(() => {
    const tr = props.session?.traces || {};
    if (props.placement === "head") return { kind: "head", pitch: tr.pitch || [], roll: tr.roll || [] };
    if (props.placement === "wrist")
      return { kind: "wrist", r: props.session?.arms?.R?.traces?.pitch || [], l: props.session?.arms?.L?.traces?.pitch || [] };
    return { kind: "body", roll: tr.roll || [] };
  }, [props.session, props.placement]);

  const len = arrays.kind === "wrist" ? (arrays.r as number[]).length : (arrays.roll as number[])?.length || (arrays as any).pitch?.length || 0;

  useEffect(() => {
    const cv = ref.current; if (!cv) return;
    const dpr = window.devicePixelRatio || 1;
    const W = cv.clientWidth || 320, H = 170;
    cv.width = W * dpr; cv.height = H * dpr;
    const ctx = cv.getContext("2d"); if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const i = Math.max(0, Math.min(len - 1, Math.round(props.index)));
    if (arrays.kind === "head") drawHead(ctx, W, H, (arrays.pitch as number[])[i] || 0, (arrays.roll as number[])[i] || 0);
    else if (arrays.kind === "body") drawBody(ctx, W, H, (arrays.roll as number[])[i] || 0);
    else drawArms(ctx, W, H, (arrays.r as number[])[i] || 0, (arrays.l as number[])[i] || 0);
  }, [props.index, arrays, len]);

  if (!len) return null;
  return (
    <div className="panel">
      <h2>{MOTION_TITLE[props.lang]}</h2>
      <p className="hint">{MOTION_HINT[props.lang][props.placement]}</p>
      <div className="ltr"><canvas ref={ref} style={{ width: "100%", height: "170px" }} /></div>
    </div>
  );
}
