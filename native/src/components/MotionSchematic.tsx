import { useEffect, useMemo, useRef } from "react";
import { MOTION_HINT, MOTION_TITLE, type Lang } from "../lib/i18n";

// Motion schematic driven by the recorded traces. Shares the Dashboard's
// playhead `index`, so play/pause/speed/scrub animate the figure and the trace
// together. Each placement gets a purpose-built view:
//   head   — two dials (roll + pitch), the original, kept.
//   sacrum — head-on torso rolling about its long axis against a flat WATER LINE,
//            so the tilt you see IS the body roll relative to the surface.
//   wrist  — side-view stroke: each forearm sweeps recovery -> catch -> pull,
//            solid below the water line (underwater pull), dashed above (recovery).
const cssv = (n: string) =>
  getComputedStyle(document.documentElement).getPropertyValue(n).trim() || "";

function waterLine(ctx: CanvasRenderingContext2D, W: number, H: number, y: number) {
  ctx.fillStyle = "rgba(74,168,255,.09)";
  ctx.fillRect(0, y, W, H - y);
  ctx.strokeStyle = "rgba(74,168,255,.55)"; ctx.lineWidth = 1.5;
  ctx.setLineDash([6, 4]);
  ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
  ctx.setLineDash([]);
}

function label(ctx: CanvasRenderingContext2D, W: number, H: number, text: string) {
  ctx.fillStyle = cssv("--muted"); ctx.font = "11px " + cssv("--mono");
  ctx.textAlign = "center"; ctx.textBaseline = "alphabetic";
  ctx.fillText(text, W / 2, H - 6);
}

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

// Head-on view (looking down the swimmer's long axis toward the head): the torso
// cross-section rolls; the flat water line is the reference, so the shoulder
// line's tilt against it is the body roll.
function drawBody(ctx: CanvasRenderingContext2D, W: number, H: number, roll: number) {
  const accent = cssv("--accent"), muted = cssv("--muted");
  const right = cssv("--right") || accent, left = cssv("--left");
  const cx = W * 0.5, cy = H * 0.52;
  waterLine(ctx, W, H, cy);

  const r = (roll * Math.PI) / 180;
  ctx.save(); ctx.translate(cx, cy); ctx.rotate(r);
  // torso cross-section (shoulders wider than deep)
  ctx.strokeStyle = muted; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.ellipse(0, 0, 44, 22, 0, 0, 2 * Math.PI); ctx.stroke();
  // shoulder line + shoulders (right = blue, left = orange)
  ctx.strokeStyle = accent; ctx.lineWidth = 3; ctx.lineCap = "round";
  ctx.beginPath(); ctx.moveTo(-44, 0); ctx.lineTo(44, 0); ctx.stroke();
  ctx.fillStyle = right; ctx.beginPath(); ctx.arc(44, 0, 6, 0, 2 * Math.PI); ctx.fill();
  ctx.fillStyle = left; ctx.beginPath(); ctx.arc(-44, 0, 6, 0, 2 * Math.PI); ctx.fill();
  // spine dot
  ctx.fillStyle = muted; ctx.beginPath(); ctx.arc(0, 0, 2.5, 0, 2 * Math.PI); ctx.fill();
  ctx.restore();

  label(ctx, W, H, "body roll " + (roll >= 0 ? "+" : "") + roll.toFixed(0) + "° vs water  ·  R blue / L orange");
}

// Side view (swimmer prone at the surface, head to the left). Each arm sweeps
// from recovery (above water, forward) through catch to pull (below water,
// back). fracR/fracL in [0,1] map recovery->pull along the recorded pitch range.
function drawArms(ctx: CanvasRenderingContext2D, W: number, H: number, fracR: number, fracL: number) {
  const right = cssv("--right") || cssv("--accent"), left = cssv("--left"), muted = cssv("--muted");
  const waterY = H * 0.4;
  waterLine(ctx, W, H, waterY);

  const shX = W * 0.52, shY = waterY + 5, L = 52;
  // torso + head at the surface, moving left
  ctx.strokeStyle = muted; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.ellipse(shX + 26, shY + 5, 30, 9, 0, 0, 2 * Math.PI); ctx.stroke();
  ctx.beginPath(); ctx.arc(shX - 30, shY + 3, 8, 0, 2 * Math.PI); ctx.stroke();

  const REC = -0.6, PULL = 2.7;  // radians: recovery (up-forward) -> pull (down-back)
  const arm = (frac: number, color: string, dx: number) => {
    const th = REC + (PULL - REC) * Math.max(0, Math.min(1, frac));
    const hx = shX + dx + Math.sin(th) * L;
    const hy = shY - Math.cos(th) * L;
    const under = hy > waterY;
    ctx.strokeStyle = color; ctx.lineWidth = 4; ctx.lineCap = "round";
    ctx.setLineDash(under ? [] : [4, 4]);
    ctx.beginPath(); ctx.moveTo(shX + dx, shY); ctx.lineTo(hx, hy); ctx.stroke();
    ctx.setLineDash([]);
    ctx.lineWidth = 2; ctx.strokeStyle = color;
    ctx.beginPath(); ctx.arc(hx, hy, 5, 0, 2 * Math.PI);
    if (under) { ctx.fillStyle = color; ctx.fill(); } else ctx.stroke();
  };
  arm(fracR, right, 3); arm(fracL, left, -3);

  label(ctx, W, H, "R blue / L orange  ·  solid = underwater pull, dashed = recovery");
}

function extent(a: number[]): [number, number] {
  const f = a.filter((x) => Number.isFinite(x));
  return f.length ? [Math.min(...f), Math.max(...f)] : [0, 1];
}

export function MotionSchematic(props: { lang: Lang; placement: string; session: any; index: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const arrays = useMemo(() => {
    const tr = props.session?.traces || {};
    if (props.placement === "head") return { kind: "head", pitch: tr.pitch || [], roll: tr.roll || [] };
    if (props.placement === "wrist") {
      const r = props.session?.arms?.R?.traces?.pitch || [];
      const l = props.session?.arms?.L?.traces?.pitch || [];
      return { kind: "wrist", r, l, rEx: extent(r), lEx: extent(l) } as const;
    }
    return { kind: "body", roll: tr.roll || [] };
  }, [props.session, props.placement]);

  const len = arrays.kind === "wrist"
    ? (arrays.r as number[]).length
    : ((arrays as any).roll?.length || (arrays as any).pitch?.length || 0);

  useEffect(() => {
    const cv = ref.current; if (!cv) return;
    const dpr = window.devicePixelRatio || 1;
    const W = cv.clientWidth || 320, H = 170;
    cv.width = W * dpr; cv.height = H * dpr;
    const ctx = cv.getContext("2d"); if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const i = Math.max(0, Math.min(len - 1, Math.round(props.index)));
    if (arrays.kind === "head") {
      drawHead(ctx, W, H, (arrays.pitch as number[])[i] || 0, (arrays.roll as number[])[i] || 0);
    } else if (arrays.kind === "body") {
      drawBody(ctx, W, H, (arrays.roll as number[])[i] || 0);
    } else {
      const norm = (v: number, ex: readonly [number, number]) => (ex[1] > ex[0] ? (v - ex[0]) / (ex[1] - ex[0]) : 0.5);
      const rEx = ((arrays as any).rEx ?? [0, 1]) as [number, number];
      const lEx = ((arrays as any).lEx ?? [0, 1]) as [number, number];
      drawArms(ctx, W, H, norm((arrays.r as number[])[i] || 0, rEx), norm((arrays.l as number[])[i] || 0, lEx));
    }
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
