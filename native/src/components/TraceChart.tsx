import { useEffect, useRef } from "react";

export type Series = { name: string; color: string; data: number[] };

// Canvas line chart of one or more time series with a vertical playhead at the
// current sample. Mirrors the web dashboards' trace panels; kept framework-free
// so it ports cleanly and stays cheap on device.
export function TraceChart(props: { t: number[]; series: Series[]; index: number; height?: number }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const cvs = ref.current;
    if (!cvs) return;
    const dpr = window.devicePixelRatio || 1;
    const W = cvs.clientWidth || 320;
    const H = props.height ?? 240;
    cvs.width = W * dpr;
    cvs.height = H * dpr;
    const g = cvs.getContext("2d");
    if (!g) return;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, W, H);

    const n = props.t.length;
    if (n < 2) return;
    const all = props.series.flatMap((s) => s.data).filter((v) => Number.isFinite(v));
    let lo = Math.min(...all), hi = Math.max(...all);
    if (!Number.isFinite(lo) || !Number.isFinite(hi) || lo === hi) { lo -= 1; hi += 1; }
    const padY = (hi - lo) * 0.08;
    lo -= padY; hi += padY;
    const x = (i: number) => (i / (n - 1)) * (W - 8) + 4;
    const y = (v: number) => H - 6 - ((v - lo) / (hi - lo)) * (H - 12);

    // zero line
    if (lo < 0 && hi > 0) {
      g.strokeStyle = "rgba(139,151,167,.35)";
      g.lineWidth = 1;
      g.beginPath(); g.moveTo(4, y(0)); g.lineTo(W - 4, y(0)); g.stroke();
    }
    // series
    for (const s of props.series) {
      g.strokeStyle = s.color;
      g.lineWidth = 1.6;
      g.beginPath();
      let started = false;
      for (let i = 0; i < n; i++) {
        const v = s.data[i];
        if (!Number.isFinite(v)) { started = false; continue; }
        const px = x(i), py = y(v);
        if (!started) { g.moveTo(px, py); started = true; } else g.lineTo(px, py);
      }
      g.stroke();
    }
    // playhead
    const pi = Math.max(0, Math.min(n - 1, props.index));
    g.strokeStyle = "var(--accent)";
    g.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue("--accent") || "#4aa8ff";
    g.lineWidth = 1.5;
    g.beginPath(); g.moveTo(x(pi), 2); g.lineTo(x(pi), H - 2); g.stroke();
  }, [props.t, props.series, props.index, props.height]);

  return <canvas ref={ref} className="trace" style={{ width: "100%", height: (props.height ?? 240) + "px" }} />;
}
