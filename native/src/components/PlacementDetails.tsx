import { STR, type Lang } from "../lib/i18n";

// Expandable per-placement detail — the full richness of the web dashboard, kept
// off-screen behind <details> so the mobile view stays clean. One tap opens the
// per-length / per-breath / per-arm tables and the L/R symmetry bars, all read
// straight from the payload the backend already returns.
const f = (x: any, d = 1) => (x == null || Number.isNaN(x) ? "—" : Number(x).toFixed(d));

// A left/right proportional bar (right = blue, left = orange).
function SymBar(props: { lang: Lang; label: string; l: number; r: number; unit?: string }) {
  const L = Math.abs(props.l || 0), R = Math.abs(props.r || 0), tot = L + R || 1;
  return (
    <div className="symrow">
      <div className="sym-label">{props.label}</div>
      <div className="symbar">
        <span className="sb-cap">{f(L, 0)}{props.unit}</span>
        <div className="sb-track">
          <div className="sb-l" style={{ width: (L / tot) * 100 + "%" }} />
          <div className="sb-r" style={{ width: (R / tot) * 100 + "%" }} />
        </div>
        <span className="sb-cap">{f(R, 0)}{props.unit}</span>
      </div>
    </div>
  );
}

function Section(props: { title: string; children: any; open?: boolean }) {
  return (
    <details className="detail" open={props.open}>
      <summary>{props.title}</summary>
      <div className="detail-body">{props.children}</div>
    </details>
  );
}

function HeadDetails({ lang, s }: { lang: Lang; s: any }) {
  const t = (k: string) => STR[lang][k] ?? k;
  const breaths: any[] = (s.breaths || []).filter((b: any) => !b.excluded);
  const mean = s.summary?.mean_d_pitch_breath ?? 0;
  const gate = s.gate_threshold_deg ?? 13.5;
  const scale = Math.max(mean, gate) * 1.4 || 1;
  return (
    <>
      <Section title={t("detGate")} open>
        <div className="gate">
          <div className="gate-track">
            <div className="gate-fill" style={{ width: Math.min(100, (mean / scale) * 100) + "%" }} />
            <div className="gate-mark" style={{ left: (gate / scale) * 100 + "%" }} />
          </div>
          <div className="gate-legend">
            <span>{t("thDpitch")} {f(mean)}°</span>
            <span className="muted">{t("gateLabel")} {f(gate, 0)}°</span>
            <b>{s.detected_pattern}</b>
          </div>
        </div>
      </Section>
      {breaths.length > 0 && (
        <Section title={`${t("detBreaths")} (${breaths.length})`}>
          <div className="tscroll">
            <table>
              <thead><tr><th>{t("thSide")}</th><th>{t("thDpitch")}</th><th>{t("thPeakRoll")}</th><th>{t("thDur")}</th></tr></thead>
              <tbody>
                {breaths.map((b, i) => (
                  <tr key={i}>
                    <td>{b.side}</td><td>{f(b.d_pitch_breath)}°</td><td>{f(b.peak_roll_breath)}°</td><td>{f(b.breath_duration, 2)}s</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}
    </>
  );
}

function SacrumDetails({ lang, s }: { lang: Lang; s: any }) {
  const t = (k: string) => STR[lang][k] ?? k;
  const lengths: any[] = s.lengths || [];
  const sm = s.summary || {};
  return (
    <>
      <Section title={t("detSymmetry")} open>
        <SymBar lang={lang} label={t("rollSym")} l={sm.mean_peak_roll_left_deg} r={sm.mean_peak_roll_right_deg} unit="°" />
      </Section>
      {lengths.length > 0 && (
        <Section title={`${t("detLengths")} (${lengths.length})`}>
          <div className="tscroll">
            <table>
              <thead><tr><th>{t("thLen")}</th><th>{t("thTime")}</th><th>{t("thStrokes")}</th></tr></thead>
              <tbody>
                {lengths.map((l, i) => (
                  <tr key={i}><td>{l.length_index + 1}</td><td>{f(l.duration_s, 1)}s</td><td>{l.strokes}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}
    </>
  );
}

function WristDetails({ lang, s }: { lang: Lang; s: any }) {
  const t = (k: string) => STR[lang][k] ?? k;
  const R = s.arms?.R?.summary || {}, L = s.arms?.L?.summary || {};
  const sym = s.symmetry || {};
  const phase = sym.mean_phase_offset_cycles;
  return (
    <>
      <Section title={t("detSymmetry")} open>
        <SymBar lang={lang} label={t("ampSym")} l={L.pitch_amplitude_deg} r={R.pitch_amplitude_deg} unit="°" />
        {phase != null && (
          <div className="phase">
            <div className="sym-label">{t("phaseLabel")}: <b>{f(phase, 2)}</b></div>
            <div className="phase-track"><div className="phase-ideal" /><div className="phase-mark" style={{ left: Math.min(100, Math.max(0, phase * 100)) + "%" }} /></div>
            <div className="muted sm">{t("phaseAnti")}</div>
          </div>
        )}
      </Section>
      <Section title={t("detArms")} open>
        <div className="tscroll">
          <table>
            <thead><tr><th>{t("thArm")}</th><th>{t("thStrokes")}</th><th>{t("thRate")}</th><th>{t("thAmp")}</th><th>{t("thPull")}</th></tr></thead>
            <tbody>
              {[["R", R], ["L", L]].map(([side, a]: any) => (
                <tr key={side}>
                  <td>{side}</td><td>{a.stroke_count ?? "—"}</td><td>{f(a.stroke_rate_cpm)}</td>
                  <td>{f(a.pitch_amplitude_deg)}°</td><td>{f(a.pull_fraction, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </>
  );
}

export function PlacementDetails(props: { lang: Lang; placement: string; session: any }) {
  const s = props.session;
  if (!s) return null;
  if (props.placement === "head") return <HeadDetails lang={props.lang} s={s} />;
  if (props.placement === "sacrum") return <SacrumDetails lang={props.lang} s={s} />;
  if (props.placement === "wrist") return <WristDetails lang={props.lang} s={s} />;
  return null;
}
