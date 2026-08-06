// Movella DOT capture for the native app.
//
// Two decode/assemble helpers here are SOLID (derived in swimlab/io.py from the
// jiminghe/Xsens_DOT_PC_Reader reference parser): the Custom-Mode-5 byte layout
// and the canonical CSV the backend reads. The BLE transport (UUIDs, control
// bytes) is a skeleton marked TODO(real-device) — validate against a real DOT
// before trusting it. Until then, use MockDotSensor / the import path, which
// feed synthetic Custom-Mode-5 CSVs through the same pipeline.
import type { Recording } from "../lib/backend";

// ---- BLE identifiers (best-effort; confirm on a real device) ----
// Xsens/Movella DOT GATT. Suffixes per firmware/app version may differ.
export const DOT = {
  MEASUREMENT_SERVICE: "15172001-4947-11e9-8646-d663bd873d93", // TODO(real-device)
  MEAS_CONTROL_CHAR: "15172002-4947-11e9-8646-d663bd873d93", // write: mode + start/stop
  MEDIUM_PAYLOAD_CHAR: "15172004-4947-11e9-8646-d663bd873d93", // notify: samples
  // Custom Mode 5 = Timestamp + Quaternion + raw Acceleration + Angular velocity.
  PAYLOAD_CUSTOM_MODE_5: 26, // payload id (TODO(real-device))
  NAME_PREFIXES: ["Movella DOT", "Xsens DOT"],
} as const;

// One decoded sample in the canonical schema (SI units, sensor frame).
export type DotSample = {
  sampleTimeFine: number; // uint32 microseconds, 1 MHz, wraps at 2^32
  quat: [number, number, number, number]; // w, x, y, z
  acc: [number, number, number]; // m/s^2, raw (WITH gravity) for Custom Mode 5
  gyr: [number, number, number]; // deg/s
};

// Decode one Custom-Mode-5 record from a DOT notification payload.
// Layout: SampleTimeFine u32 | Quat 4xf32(w,x,y,z) | Acc 3xf32 | Gyr 3xf32, LE.
export function decodeCustomMode5(view: DataView, offset = 0): DotSample {
  const LE = true;
  let o = offset;
  const sampleTimeFine = view.getUint32(o, LE); o += 4;
  const f = () => { const v = view.getFloat32(o, LE); o += 4; return v; };
  const quat: [number, number, number, number] = [f(), f(), f(), f()];
  const acc: [number, number, number] = [f(), f(), f()];
  const gyr: [number, number, number] = [f(), f(), f()];
  return { sampleTimeFine, quat, acc, gyr };
}

export const CUSTOM5_COLUMNS = [
  "SampleTimeFine",
  "Quat_W", "Quat_X", "Quat_Y", "Quat_Z",
  "Acc_X", "Acc_Y", "Acc_Z",
  "Gyr_X", "Gyr_Y", "Gyr_Z",
] as const;

// Assemble decoded samples into a Custom-Mode-5 CSV the backend (io.py) reads.
export function assembleCustomMode5Csv(samples: DotSample[]): string {
  const rows = samples.map((s) =>
    [s.sampleTimeFine, ...s.quat, ...s.acc, ...s.gyr]
      .map((n, i) => (i === 0 ? String(n) : Number(n).toPrecision(8)))
      .join(","),
  );
  return [CUSTOM5_COLUMNS.join(","), ...rows].join("\n") + "\n";
}

// ---- the capture interface ----
export type Placement =
  | "head" | "sacrum" | "wrist_l" | "wrist_r"
  | "ankle_l" | "ankle_r" | "uparm_l" | "uparm_r";

export interface DotSensor {
  /** Connect (BLE) or prepare (mock). */
  connect(): Promise<void>;
  /** Record a trial + T0a/T0b calibration for one placement -> a Recording. */
  capture(placement: Placement, opts?: { swimmerId?: string }): Promise<Recording>;
  disconnect(): Promise<void>;
}

// Mock sensor: turns pre-supplied Custom-Mode-5 CSVs into Recordings, so the
// whole app (process -> dashboards -> narrate -> save) works with no hardware.
export class MockDotSensor implements DotSensor {
  constructor(private csvs: Record<Placement, { trial: string; t0a: string; t0b: string }>) {}
  async connect() {}
  async capture(placement: Placement, opts: { swimmerId?: string } = {}): Promise<Recording> {
    const c = this.csvs[placement];
    if (!c) throw new Error(`no mock CSVs for placement ${placement}`);
    return { placement_id: placement, trial: c.trial, t0a: c.t0a, t0b: c.t0b, swimmer_id: opts.swimmerId };
  }
  async disconnect() {}
}

// Real BLE sensor skeleton. Uses @capacitor-community/bluetooth-le. The control
// write + notification framing are TODO(real-device); the decode/assemble above
// are ready. Onboard 120 Hz recording is preferred (BLE streaming caps ~60 Hz
// and drops underwater) — a later revision offloads the onboard file instead of
// live-streaming; this streams as a first bring-up path.
export class BleDotSensor implements DotSensor {
  private deviceId?: string;
  private samples: DotSample[] = [];

  async connect(): Promise<void> {
    const { BleClient } = await import("@capacitor-community/bluetooth-le");
    await BleClient.initialize();
    const device = await BleClient.requestDevice({ services: [DOT.MEASUREMENT_SERVICE] });
    this.deviceId = device.deviceId;
    await BleClient.connect(this.deviceId);
  }

  private async record(seconds: number): Promise<DotSample[]> {
    const { BleClient, numbersToDataView } = await import("@capacitor-community/bluetooth-le");
    if (!this.deviceId) throw new Error("not connected");
    this.samples = [];
    await BleClient.startNotifications(
      this.deviceId, DOT.MEASUREMENT_SERVICE, DOT.MEDIUM_PAYLOAD_CHAR,
      (value) => this.samples.push(decodeCustomMode5(value)),
    );
    // TODO(real-device): exact control bytes to select Custom Mode 5 + start.
    const start = numbersToDataView([1, 1, DOT.PAYLOAD_CUSTOM_MODE_5]);
    await BleClient.write(this.deviceId, DOT.MEASUREMENT_SERVICE, DOT.MEAS_CONTROL_CHAR, start);
    await new Promise((r) => setTimeout(r, seconds * 1000));
    const stop = numbersToDataView([1, 0, 0]);
    await BleClient.write(this.deviceId, DOT.MEASUREMENT_SERVICE, DOT.MEAS_CONTROL_CHAR, stop);
    await BleClient.stopNotifications(this.deviceId, DOT.MEASUREMENT_SERVICE, DOT.MEDIUM_PAYLOAD_CHAR);
    return this.samples.slice();
  }

  async capture(placement: Placement, opts: { swimmerId?: string } = {}): Promise<Recording> {
    // A real protocol prompts for the T0a/T0b poses; here we record three clips.
    const t0a = assembleCustomMode5Csv(await this.record(3));
    const t0b = assembleCustomMode5Csv(await this.record(3));
    const trial = assembleCustomMode5Csv(await this.record(30));
    return { placement_id: placement, trial, t0a, t0b, swimmer_id: opts.swimmerId };
  }

  async disconnect(): Promise<void> {
    if (!this.deviceId) return;
    const { BleClient } = await import("@capacitor-community/bluetooth-le");
    await BleClient.disconnect(this.deviceId);
    this.deviceId = undefined;
  }
}

// Group loose CSV files (from a file picker) into Recordings by name/path —
// same convention as the web Import: head/trial.csv, sacrum/t0a.csv, ….
const PLACEMENT_RE = /(wrist_l|wrist_r|ankle_l|ankle_r|uparm_l|uparm_r|head|sacrum)/i;
export async function filesToRecordings(
  files: { name: string; text: () => Promise<string> }[],
): Promise<{ recordings: Recording[]; unmatched: string[] }> {
  const groups: Record<string, any> = {};
  const unmatched: string[] = [];
  for (const f of files) {
    const name = f.name.toLowerCase();
    const pm = name.match(PLACEMENT_RE);
    const role = /t0a/.test(name) ? "t0a" : /t0b/.test(name) ? "t0b"
      : /trial|swim|t7/.test(name) ? "trial" : null;
    if (!pm || !role) { unmatched.push(f.name); continue; }
    const pid = pm[1];
    (groups[pid] = groups[pid] || { placement_id: pid })[role] = await f.text();
  }
  const recordings = Object.values(groups).filter(
    (g: any) => g.trial && g.t0a && g.t0b,
  ) as Recording[];
  for (const g of Object.values(groups) as any[]) {
    if (!(g.trial && g.t0a && g.t0b)) unmatched.push(`${g.placement_id} (needs trial+t0a+t0b)`);
  }
  return { recordings, unmatched };
}
