// Thin client over the deployed swimlab Cloud Functions + account data. Mirrors
// the web app's window.SwimBackend / SwimData so the two stay behaviourally in
// sync. The auth token auto-attaches to callables when signed in.
import { httpsCallable } from "firebase/functions";
import { collection, getDocs, orderBy, query } from "firebase/firestore";
import { getBytes, ref } from "firebase/storage";
import { auth, db, functions, storage } from "./firebase";

export type Recording = {
  placement_id: string;
  trial: string;
  t0a?: string; // omitted for single-file capture (backend derives calibration)
  t0b?: string;
  swimmer_id?: string;
  mount_offset_deg?: number[];
};

export type Bundle = {
  placements: Record<string, { sessions: Record<string, any>; default: string }>;
  default_placement?: string;
  saved?: { swim_id: string; bundlePath: string };
  saveError?: string;
};

export type SwimDoc = {
  id: string;
  swimmer_id?: string;
  pool_length_m?: number;
  createdAt?: { seconds: number } | string;
  default_placement?: string;
  summary?: { placements?: string[]; per_placement?: Record<string, any> };
  bundlePath?: string;
};

const _process = httpsCallable(functions, "process_session", { timeout: 300000 });
const _narrate = httpsCallable(functions, "narrate", { timeout: 120000 });
const _detect = httpsCallable(functions, "detect_placement", { timeout: 60000 });

export type Detection = {
  placement: "head" | "sacrum" | "wrist";
  confidence: number;
  scores: Record<string, number>;
  features: Record<string, number>;
};

// Infer a sensor's placement type from one raw recording (side stays user-confirmed).
export async function detectPlacement(csv: string): Promise<Detection> {
  const { data } = await _detect({ csv });
  return data as Detection;
}

export async function processSession(
  recordings: Recording[],
  opts: { poolLengthM?: number; swimId?: string } = {},
): Promise<Bundle> {
  const body: Record<string, unknown> = {
    recordings,
    pool_length_m: opts.poolLengthM ?? 25,
  };
  if (opts.swimId) body.swim_id = opts.swimId;
  const { data } = await _process(body);
  return data as Bundle;
}

export type Narration = { narratives: { en: any; he: any }; model: string; placement: string; tier?: string };

export async function narrate(payload: any, placement?: string): Promise<Narration> {
  const { data } = await _narrate({ payload, placement });
  return data as Narration;
}

export async function listSwims(): Promise<SwimDoc[]> {
  const u = auth.currentUser;
  if (!u) return [];
  const q = query(collection(db, "users", u.uid, "swims"), orderBy("createdAt", "desc"));
  const snap = await getDocs(q);
  return snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<SwimDoc, "id">) }));
}

export async function loadBundle(bundlePath: string): Promise<Bundle> {
  const bytes = await getBytes(ref(storage, bundlePath));
  return JSON.parse(new TextDecoder().decode(bytes)) as Bundle;
}

// Reopen a saved swim via the backend (Admin SDK reads Storage server-side, so
// there's no browser-CORS problem the direct download had).
const _getSwim = httpsCallable(functions, "get_swim", { timeout: 60000 });
export async function getSwim(swimId: string): Promise<Bundle> {
  const { data } = await _getSwim({ swim_id: swimId });
  return data as Bundle;
}

export function isUpgradeRequired(err: any): boolean {
  const code = (err && (err.code || "")) as string;
  return code.includes("permission-denied") || err?.details?.reason === "upgrade_required";
}
