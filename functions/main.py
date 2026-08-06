"""Firebase Cloud Functions (Python, 2nd gen) — the swimlab backend.

Wraps the validated ``swimlab`` engine so the app can process real Movella DOT
recordings and get AI narration **without** a worker URL or a client-side API
key. Two callable endpoints:

* ``process_session`` — Custom-Mode-5 recordings per placement -> dashboard
  payloads (head / sacrum / wrist, with L/R fusion). Free tier.
* ``narrate`` — server-side, placement-aware Anthropic narration (EN + HE). The
  Anthropic key is a Firebase **secret**, never sent to the client. Paid tier.

Deploy notes: the ``swimlab`` engine must be importable in the function runtime.
Run ``./vendor_swimlab.sh`` first (copies the engine + config.yaml into
``vendor/``, which is git-ignored and added to ``sys.path`` below). See README.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make a vendored copy of the swimlab engine importable (see vendor_swimlab.sh).
_VENDOR = Path(__file__).resolve().parent / "vendor"
if _VENDOR.is_dir():
    sys.path.insert(0, str(_VENDOR))

from firebase_functions import https_fn, options  # noqa: E402
from firebase_functions.params import SecretParam  # noqa: E402

from swimbackend import narrate as narrate_mod  # noqa: E402
from swimbackend import pipeline  # noqa: E402

ANTHROPIC_API_KEY = SecretParam("ANTHROPIC_API_KEY")

# Lock CORS/callable access to the app origins (adjust to your Hosting domains).
_CORS = options.CorsOptions(cors_origins="*", cors_methods=["POST", "OPTIONS"])


def _resolve_recordings(recordings: list[dict]) -> list[dict]:
    """Each recording's ``trial``/``t0a``/``t0b`` may be inline CSV text or a
    ``gs://`` Storage path. Resolve Storage paths to text (large real files live
    in Storage, not inline in the request)."""
    def _resolve(v: str) -> str:
        if isinstance(v, str) and v.startswith("gs://"):
            from firebase_admin import storage  # lazy: only when needed
            _, _, rest = v.partition("gs://")
            bucket_name, _, blob_path = rest.partition("/")
            blob = storage.bucket(bucket_name).blob(blob_path)
            return blob.download_as_text()
        return v

    out = []
    for r in recordings:
        out.append({**r, **{k: _resolve(r[k]) for k in ("trial", "t0a", "t0b") if k in r}})
    return out


@https_fn.on_call(memory=options.MemoryOption.MB_512, timeout_sec=300, cors=_CORS)
def process_session(req: https_fn.CallableRequest):
    """Process a swim's recordings -> dashboard bundle. Free tier.

    Request data: ``{recordings: [{placement_id, trial, t0a, t0b, ...}],
    pool_length_m?: number}`` where each CSV field is inline text or a ``gs://``
    path. Returns the app-bundle shape ``{placements: {...}, default_placement}``.
    """
    data = req.data or {}
    recordings = data.get("recordings")
    if not recordings:
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
                                  "recordings[] required")
    pool = float(data.get("pool_length_m", 25.0))
    try:
        recs = _resolve_recordings(recordings)
        return pipeline.process_session(recs, pool_length_m=pool)
    except Exception as e:  # surface a clean error to the client
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.INTERNAL, f"processing failed: {e}")


@https_fn.on_call(secrets=[ANTHROPIC_API_KEY], memory=options.MemoryOption.MB_512,
                  timeout_sec=120, cors=_CORS)
def narrate(req: https_fn.CallableRequest):
    """Server-side AI narration for one placement payload. Paid tier.

    Request data: ``{payload: <dashboard payload>, placement?: str}``. Returns
    ``{narratives: {en, he}, model, placement}`` — both languages, so the app's
    EN/HE toggle stays instant. The Anthropic key is a server secret.

    (Phase A: two single-language calls. TODO: switch to the worker's one-call
    dual-translation for lower cost.)
    """
    data = req.data or {}
    payload = data.get("payload")
    if not payload:
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.INVALID_ARGUMENT, "payload required")
    placement = data.get("placement") or narrate_mod.detect_placement(payload)
    key = ANTHROPIC_API_KEY.value
    try:
        narratives = {}
        model = None
        for lang in ("en", "he"):
            n = narrate_mod.narrate_payload(payload, placement=placement, api_key=key, lang=lang)
            model = n.pop("model", model)
            n.pop("lang", None); n.pop("placement", None)
            narratives[lang] = n
        return {"narratives": narratives, "model": model, "placement": placement}
    except Exception as e:
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.INTERNAL, f"narration failed: {e}")
