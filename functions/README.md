# swimlab backend — Firebase Cloud Functions (Python)

Phase A of the app (see `../docs/app-architecture.md`): the validated `swimlab`
engine behind two Python Cloud Functions, so the app processes real Movella DOT
recordings and gets AI narration with **no worker URL and no client-side API
key**.

```
functions/
  main.py                 Cloud Function handlers: process_session, narrate
  swimbackend/
    pipeline.py           CSV recordings -> dashboard payloads (pure, testable)
    findings.py           rule-based coaching (vendored from src/, keep in sync)
    narrate.py            placement-aware Anthropic narration (vendored, keep in sync)
  tests/                  end-to-end tests on synthetic data (no Firebase needed)
  requirements.txt
  vendor_swimlab.sh       copies the swimlab engine into ./vendor for the runtime
```

## Endpoints (callable)

| Function | Tier | In | Out |
|---|---|---|---|
| `process_session` | free | `{recordings: [{placement_id, trial, t0a, t0b, ...}], pool_length_m?, swim_id?}` | `{placements: {head,sacrum,wrist}, default_placement, saved?}` |
| `detect_placement` | free | `{csv}` (inline or `gs://`) | `{placement: 'head'\|'sacrum'\|'wrist', confidence, scores, features}` |
| `narrate` | paid* | `{payload, placement?}` | `{narratives: {en, he}, model, placement, tier}` |
| `set_tier` | admin | `{uid, tier: 'free'\|'paid'}` | `{uid, tier}` |

`detect_placement` infers the placement *type* from one raw recording
(calibration-free features → nearest synth-tuned centroid; see
`placement_detect.py`). Side (L/R) isn't inferable from one sensor — the caller
confirms it. Head-vs-sacrum is correct ~99% on synth but with a lower, honest
confidence that drives the app's infer-and-confirm UI. `# TODO(real-file)`:
reconfirm the centroids on a real export.

Each recording's `trial`/`t0a`/`t0b` is a **Custom-Mode-5 CSV** — inline text, or
a `gs://` Storage path (large real files live in Storage; `process_session`
downloads them). `wrist_l` + `wrist_r` are fused into one `wrist` payload.

**Two capture shapes** per recording (see `pipeline._calib_frames`):

- **Calibration set** — `trial` + `t0a` + `t0b` (the validated path).
- **Single file** — `trial` only. The first `_SINGLE_FILE_CAL_WINDOW_S` seconds
  are taken **provisionally** as the two calibration poses (first half T0a,
  second half T0b) and the remainder is the swim; the payload is flagged
  `CALIB_FROM_TRIAL_PROVISIONAL`. Window/pose-order are `# TODO(real-file)` —
  locked once a real DOT export confirms how calibration is recorded.

### Accounts & entitlements (Phase C)

- **Auth is attributed, not required.** Anonymous/unauthenticated calls still
  work (the demo + smoke path). When the caller is signed in **and** passes a
  `swim_id`, `process_session` saves the swim to their account via the Admin SDK:
  the full bundle to Storage `users/{uid}/swims/{swimId}/bundle.json`, and a
  summary + raw refs to Firestore `users/{uid}/swims/{swimId}` (see
  `../firestore.rules` and `../docs/app-architecture.md §3a`). The response gains
  `saved: {swim_id, bundlePath}`.
- **\*Soft gate.** `narrate` resolves the caller's tier from
  `users/{uid}/private/entitlement` (minting `free` on first use). With
  `FREEMIUM_ENFORCED=false` (default) everyone may narrate; set it to `true` to
  enforce — free callers then get `PERMISSION_DENIED` + `{reason:"upgrade_required"}`.
  Entitlement is server-authoritative; the client can't write it.
- **`set_tier`** flips a user free↔paid for testing (caller must be in the
  `ADMIN_UIDS` env list). Replaced by a billing webhook later. You can also flip
  it by hand in the Firestore console (owner writes bypass rules).

Env (set on the functions, e.g. via `firebase functions:config` successor —
`.env` files or `options.set_global_options`, or the console):

```
FREEMIUM_ENFORCED=false        # true => enforce the paywall
ADMIN_UIDS=<your-uid>[,<uid>]  # who may call set_tier
```

## Test locally (no Firebase)

The processing core is pure Python and fully exercised on synthetic data:

```bash
pip install -e /path/to/swimlab          # the engine
cd functions && python -m pytest tests -q
```

The tests generate a synthetic swimmer → `io.write_dot_export` Custom-Mode-5 CSVs
→ `process_session`, and check the payloads + that metrics equal the direct
engine.

## Sample data + smoke-test the function

Generate real-format **Custom-Mode-5** recordings for a synthetic swimmer (a
trial + T0a/T0b per placement) and a ready-to-POST request body:

```bash
python tools/make_sample_recordings.py --out /tmp/swim_sample --n-lengths 2
# -> /tmp/swim_sample/{head,sacrum,wrist_l,wrist_r}/{trial,t0a,t0b}.csv
#    /tmp/swim_sample/request.json   (the {data:{recordings,pool_length_m}} body)
```

With the emulator running, call the function with that body:

```bash
curl -X POST \
  http://localhost:5001/<PROJECT>/us-central1/process_session \
  -H "Content-Type: application/json" -d @/tmp/swim_sample/request.json
# -> {"result": {"placements": {"head":..,"sacrum":..,"wrist":..}, "default_placement":"sacrum"}}
```

> Inline CSVs make the body a few MB per sensor — fine for a local smoke test, but
> **real recordings upload to Cloud Storage** and pass `gs://…` paths (the function
> downloads them). For a tiny curl test, generate with `--n-lengths 1` or trim
> `request.json` to a single placement.

## Deploy / emulate

**1. Create the Python venv (required).** Firebase runs Python functions from a
virtualenv at `functions/venv`; the CLI does not always create it (and fails with
`spawn ...venv\Scripts\activate.bat ENOENT` if missing). Create it with a Python
that matches `firebase.json` `runtime` (currently `python311`):

```bash
cd functions
python -m venv venv                       # py -3.11 -m venv venv  if 3.11 isn't default
source venv/Scripts/activate              # Windows/Git Bash;  venv/bin/activate on macOS/Linux
pip install -r requirements.txt
```

If your Python is 3.12, either use 3.11 here or set `firebase.json` →
`"runtime": "python312"` — the venv Python and the runtime pin must agree.

**2. Vendor the engine** so the function can import `swimlab` (git-ignored). Use
the engine branch that has the multi-placement modules
(`claude/synth-head-imu-generator-3tljlr`), not `main`:

```bash
./vendor_swimlab.sh /path/to/swimlab     # copies swimlab/ + config.yaml -> vendor/
```

**3.** Set the Anthropic key as a **secret** (never in code or client):

```bash
firebase functions:secrets:set ANTHROPIC_API_KEY
```

Then, from the repo root (with `.firebaserc` pointing at your project — copy
`.firebaserc.example`):

```bash
firebase emulators:start --only functions,firestore,storage   # local
firebase deploy --only functions,firestore,storage            # live
```

## How the app calls it (Phase B — wired)

The hosted web app (`../index.html`, built from `../src/app_template.html`) now
talks to these functions directly. To turn it on, drop your Firebase **web
config** next to the app:

```bash
cp ../firebase-config.example.js ../firebase-config.js   # git-ignored
# paste Project Settings -> Your apps -> Web app -> SDK config into it
```

The app loads `/firebase-config.js` before boot; when present it lazy-imports the
Firebase JS SDK from gstatic and exposes `window.SwimBackend`:

```js
// what the app's bootstrap sets up (src/app_template.html):
const fns = getFunctions(app, cfg.functionsRegion || "us-central1");
window.SwimBackend = {
  processSession: (recordings, poolLengthM = 25) =>
    httpsCallable(fns, "process_session")({ recordings, pool_length_m: poolLengthM }).then(r => r.data),
  narrate: (payload, placement) =>
    httpsCallable(fns, "narrate")({ payload, placement }).then(r => r.data),
};
```

With that in place:

- **Narrate ✨** calls `narrate` server-side (no worker URL, no client key). With
  no config it falls back to the Cloudflare worker / rule-based findings.
- **Import** accepts raw Movella DOT recordings — a `request.json` manifest (from
  `tools/make_sample_recordings.py`) or a set of `*.csv` named by placement/pose
  (`head/trial.csv`, `sacrum/t0a.csv`, `wrist_l/t0b.csv`, …) — and runs them
  through `process_session`, then renders the returned bundle. Exported session
  JSON still imports directly.

For local dev against the emulator, set in `firebase-config.js`:
`window.SWIMLAB_FUNCTIONS_EMULATOR = "localhost:5001";`

The key stays a server secret; free vs paid is enforced on the account in Phase C
(Firebase Auth).

## Notes

- **Firestore + Storage** (accounts, history, raw files) are Phase C; the Phase-A
  functions here are stateless. Rules are scaffolded in `../firestore.rules` /
  `../storage.rules`.
- `findings.py` / `narrate.py` are vendored copies of `../src/` — keep them in
  sync (same discipline as the Cloudflare worker).
- Narration currently makes two single-language calls; a follow-up switches to
  the worker's one-call EN→HE translation for lower cost.
