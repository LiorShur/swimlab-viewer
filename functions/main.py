"""Firebase Cloud Functions (Python, 2nd gen) — the swimlab backend.

Wraps the validated ``swimlab`` engine so the app can process real Movella DOT
recordings and get AI narration **without** a worker URL or a client-side API
key. Callable endpoints:

* ``process_session`` — Custom-Mode-5 recordings per placement -> dashboard
  payloads (head / sacrum / wrist, with L/R fusion). Free tier. When the caller
  is signed in and passes a ``swim_id``, the swim is **saved to their account**
  (bundle -> Storage, summary + refs -> Firestore) via the Admin SDK.
* ``narrate`` — server-side, placement-aware Anthropic narration (EN + HE). The
  Anthropic key is a Firebase **secret**, never sent to the client. Paid tier,
  gated by the caller's entitlement (soft during construction — see
  ``FREEMIUM_ENFORCED``).
* ``set_tier`` — admin-only: flip a user's entitlement free<->paid for testing.

Deploy notes: the ``swimlab`` engine must be importable in the function runtime.
Run ``./vendor_swimlab.sh`` first (copies the engine + config.yaml into
``vendor/``, git-ignored, added to ``sys.path`` below). See README.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make a vendored copy of the swimlab engine importable (see vendor_swimlab.sh).
_VENDOR = Path(__file__).resolve().parent / "vendor"
if _VENDOR.is_dir():
    sys.path.insert(0, str(_VENDOR))

import firebase_admin  # noqa: E402
from firebase_admin import firestore, storage  # noqa: E402
from firebase_functions import https_fn, options  # noqa: E402
from firebase_functions.params import SecretParam  # noqa: E402

from swimbackend import narrate as narrate_mod  # noqa: E402
from swimbackend import pipeline  # noqa: E402
from swimbackend import placement_detect  # noqa: E402

# Initialise the Admin SDK once (Firestore + Storage access from the function).
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app()

ANTHROPIC_API_KEY = SecretParam("ANTHROPIC_API_KEY")

# Lock CORS/callable access to the app origins (adjust to your Hosting domains).
_CORS = options.CorsOptions(cors_origins="*", cors_methods=["POST", "OPTIONS"])

# Soft gate during construction: when false, any signed-in (or anonymous) caller
# may narrate; the tier is still resolved for telemetry/upsell. Flip to "true"
# (env var) to enforce the paywall with no client change.
FREEMIUM_ENFORCED = os.environ.get("FREEMIUM_ENFORCED", "false").lower() == "true"
# Comma-separated uids allowed to call set_tier (yourself, during testing).
ADMIN_UIDS = {u.strip() for u in os.environ.get("ADMIN_UIDS", "").split(",") if u.strip()}


# ---------------------------------------------------------------- auth / tier

def _uid(req: https_fn.CallableRequest) -> str | None:
    """The caller's Firebase uid, or None if unauthenticated."""
    return req.auth.uid if getattr(req, "auth", None) else None


def _ensure_entitlement(uid: str) -> str:
    """Read the user's tier, creating a default 'free' entitlement on first use.

    Entitlement is server-authoritative (the client can't write it — see
    firestore.rules), so this is the only place a 'free' default is minted.
    """
    db = firestore.client()
    ref = db.document(f"users/{uid}/private/entitlement")
    snap = ref.get()
    if snap.exists:
        return (snap.to_dict() or {}).get("tier", "free")
    ref.set({"tier": "free", "source": "default", "updatedAt": firestore.SERVER_TIMESTAMP})
    return "free"


def _tier(uid: str | None) -> str:
    """Resolve a caller's tier; anonymous/unauthenticated is treated as free."""
    if not uid:
        return "free"
    try:
        return _ensure_entitlement(uid)
    except Exception:
        return "free"  # never let entitlement lookup break the request path


# ---------------------------------------------------------------- persistence

def _resolve_recordings(recordings: list[dict]) -> list[dict]:
    """Each recording's ``trial``/``t0a``/``t0b`` may be inline CSV text or a
    ``gs://`` Storage path. Resolve Storage paths to text (large real files live
    in Storage, not inline in the request)."""
    def _resolve(v: str) -> str:
        if isinstance(v, str) and v.startswith("gs://"):
            _, _, rest = v.partition("gs://")
            bucket_name, _, blob_path = rest.partition("/")
            return storage.bucket(bucket_name).blob(blob_path).download_as_text()
        return v

    out = []
    for r in recordings:
        out.append({**r, **{k: _resolve(r[k]) for k in ("trial", "t0a", "t0b") if k in r}})
    return out


def _swim_summary(bundle: dict) -> dict:
    """A small, history-card-sized digest of a processed bundle (no traces)."""
    placements = bundle.get("placements", {})
    per = {}
    for pid, pl in placements.items():
        sessions = pl.get("sessions", {})
        sess = sessions.get(pl.get("default")) or next(iter(sessions.values()), {})
        summ = sess.get("summary", {}) if isinstance(sess, dict) else {}
        per[pid] = {
            "detected_pattern": sess.get("detected_pattern") if isinstance(sess, dict) else None,
            # a couple of headline numbers, whichever the placement has
            **{k: summ[k] for k in ("mean_d_pitch_breath", "distance_m", "lengths",
                                    "stroke_count", "body_roll_amplitude_deg")
               if isinstance(summ, dict) and k in summ},
        }
    return {"placements": list(placements.keys()), "per_placement": per}


def _store_raw(uid: str, swim_id: str, recordings: list[dict]) -> dict:
    """Retain the raw recordings for reprocessing. gs:// paths are kept as-is;
    inline CSV text is uploaded to users/{uid}/raw/{swimId}/{placement}/{pose}.csv.
    Returns ``{placement_id: {pose: gs://…}}``."""
    bucket = storage.bucket()
    refs: dict = {}
    for r in recordings:
        pid = r.get("placement_id", "unknown")
        refs[pid] = {}
        for pose in ("trial", "t0a", "t0b"):
            v = r.get(pose)
            if not isinstance(v, str):
                continue
            if v.startswith("gs://"):
                refs[pid][pose] = v
            else:
                path = f"users/{uid}/raw/{swim_id}/{pid}/{pose}.csv"
                bucket.blob(path).upload_from_string(v, content_type="text/csv")
                refs[pid][pose] = f"gs://{bucket.name}/{path}"
    return refs


def _persist_swim(uid: str, swim_id: str, bundle: dict, recordings: list[dict],
                  pool: float) -> str:
    """Save a processed swim to the user's account. The full bundle spills to
    Storage (it can exceed Firestore's 1 MB doc limit); Firestore holds the
    summary + pointers. Returns the bundle's gs:// path."""
    bucket = storage.bucket()
    import json
    bundle_path = f"users/{uid}/swims/{swim_id}/bundle.json"
    bucket.blob(bundle_path).upload_from_string(
        json.dumps(bundle), content_type="application/json")
    bundle_uri = f"gs://{bucket.name}/{bundle_path}"

    swimmer_id = next((r.get("swimmer_id") for r in recordings if r.get("swimmer_id")), None)
    firestore.client().document(f"users/{uid}/swims/{swim_id}").set({
        "swimmer_id": swimmer_id,
        "pool_length_m": pool,
        "createdAt": firestore.SERVER_TIMESTAMP,
        "default_placement": bundle.get("default_placement"),
        "summary": _swim_summary(bundle),
        "bundlePath": bundle_uri,
        "raw": _store_raw(uid, swim_id, recordings),
    })
    return bundle_uri


# ---------------------------------------------------------------- callables

@https_fn.on_call(memory=options.MemoryOption.MB_512, timeout_sec=300, cors=_CORS)
def process_session(req: https_fn.CallableRequest):
    """Process a swim's recordings -> dashboard bundle. Free tier.

    Request data: ``{recordings: [{placement_id, trial, t0a, t0b, ...}],
    pool_length_m?, swim_id?}``. CSV fields are inline text or ``gs://`` paths.
    Returns ``{placements, default_placement, saved?: {swim_id, bundlePath}}``.
    When signed in and a ``swim_id`` is given, the swim is saved to the account.
    """
    data = req.data or {}
    recordings = data.get("recordings")
    if not recordings:
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
                                  "recordings[] required")
    pool = float(data.get("pool_length_m", 25.0))
    uid = _uid(req)
    swim_id = data.get("swim_id")
    try:
        recs = _resolve_recordings(recordings)
        bundle = pipeline.process_session(recs, pool_length_m=pool)
    except Exception as e:  # surface a clean error to the client
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.INTERNAL, f"processing failed: {e}")

    # Persist to the account when signed in and asked to (soft: anonymous/no-id
    # calls still work, e.g. the demo/smoke path).
    if uid and swim_id:
        try:
            uri = _persist_swim(uid, str(swim_id), bundle, recs, pool)
            bundle["saved"] = {"swim_id": str(swim_id), "bundlePath": uri}
        except Exception as e:
            # Don't fail the whole request if only the save failed — return the
            # bundle with a note so the client can surface it.
            bundle["saveError"] = str(e)
    return bundle


@https_fn.on_call(memory=options.MemoryOption.MB_512, timeout_sec=60, cors=_CORS)
def detect_placement(req: https_fn.CallableRequest):
    """Infer a sensor's placement from one raw recording (for infer-and-confirm).

    Request data: ``{csv}`` — inline Custom-Mode-5 text or a ``gs://`` path.
    Returns ``{placement: 'head'|'sacrum'|'wrist', confidence, scores, features}``.
    The caller confirms the side (L/R) — that isn't inferable from one sensor.
    """
    data = req.data or {}
    csv = data.get("csv") or data.get("trial")
    if not csv:
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.INVALID_ARGUMENT, "csv required")
    try:
        text = _resolve_recordings([{"trial": csv}])[0]["trial"]  # resolves gs:// or passes text
        return placement_detect.infer_placement(pipeline._read_csv(text))
    except Exception as e:
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.INTERNAL, f"detection failed: {e}")


@https_fn.on_call(memory=options.MemoryOption.MB_512, timeout_sec=60, cors=_CORS)
def get_swim(req: https_fn.CallableRequest):
    """Return a saved swim's full dashboard bundle. Reads the bundle from Storage
    with the Admin SDK (server-side — no browser CORS), so History can reopen a
    swim reliably. Request data: ``{swim_id}``. Requires the owning user.
    """
    uid = _uid(req)
    if not uid:
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.UNAUTHENTICATED, "sign in required")
    swim_id = (req.data or {}).get("swim_id")
    if not swim_id:
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.INVALID_ARGUMENT, "swim_id required")
    snap = firestore.client().document(f"users/{uid}/swims/{swim_id}").get()
    if not snap.exists:
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.NOT_FOUND, "swim not found")
    path = (snap.to_dict() or {}).get("bundlePath")
    if not path:
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.NOT_FOUND, "swim bundle missing")
    try:
        import json
        text = _resolve_recordings([{"trial": path}])[0]["trial"]  # downloads gs://
        return json.loads(text)
    except Exception as e:
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.INTERNAL, f"load failed: {e}")


@https_fn.on_call(secrets=[ANTHROPIC_API_KEY], memory=options.MemoryOption.MB_512,
                  timeout_sec=120, cors=_CORS)
def narrate(req: https_fn.CallableRequest):
    """Server-side AI narration for one placement payload. Paid tier.

    Request data: ``{payload: <dashboard payload>, placement?}``. Returns
    ``{narratives: {en, he}, model, placement, tier}``. The Anthropic key is a
    server secret. Gating is **soft** during construction: when
    ``FREEMIUM_ENFORCED`` is off, any caller may narrate; when on, only 'paid'
    entitlements pass (others get PERMISSION_DENIED with an upgrade message).

    (Phase A: two single-language calls. TODO: switch to the worker's one-call
    dual-translation for lower cost.)
    """
    data = req.data or {}
    payload = data.get("payload")
    if not payload:
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.INVALID_ARGUMENT, "payload required")

    tier = _tier(_uid(req))
    if FREEMIUM_ENFORCED and tier != "paid":
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.PERMISSION_DENIED,
            "AI narration is a paid feature. Upgrade to unlock it.",
            {"reason": "upgrade_required", "tier": tier})

    placement = data.get("placement") or narrate_mod.detect_placement(payload)
    key = ANTHROPIC_API_KEY.value
    try:
        narratives, model = {}, None
        for lang in ("en", "he"):
            n = narrate_mod.narrate_payload(payload, placement=placement, api_key=key, lang=lang)
            model = n.pop("model", model)
            n.pop("lang", None); n.pop("placement", None)
            narratives[lang] = n
        return {"narratives": narratives, "model": model, "placement": placement, "tier": tier}
    except Exception as e:
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.INTERNAL, f"narration failed: {e}")


@https_fn.on_call(cors=_CORS)
def set_tier(req: https_fn.CallableRequest):
    """Admin-only: set a user's entitlement tier (for testing the paid path).

    Request data: ``{uid: str, tier: 'free'|'paid'}``. Caller must be in
    ``ADMIN_UIDS``. In production this is replaced by a billing webhook.
    """
    caller = _uid(req)
    if not caller or caller not in ADMIN_UIDS:
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.PERMISSION_DENIED, "admin only")
    data = req.data or {}
    target, tier = data.get("uid"), data.get("tier")
    if not target or tier not in ("free", "paid"):
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
                                  "uid and tier ('free'|'paid') required")
    firestore.client().document(f"users/{target}/private/entitlement").set(
        {"tier": tier, "source": f"admin:{caller}", "updatedAt": firestore.SERVER_TIMESTAMP})
    return {"uid": target, "tier": tier}
