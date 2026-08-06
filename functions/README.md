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
| `process_session` | free | `{recordings: [{placement_id, trial, t0a, t0b, ...}], pool_length_m?}` | `{placements: {head,sacrum,wrist}, default_placement}` |
| `narrate` | paid | `{payload, placement?}` | `{narratives: {en, he}, model, placement}` |

Each recording's `trial`/`t0a`/`t0b` is a **Custom-Mode-5 CSV** — inline text, or
a `gs://` Storage path (large real files live in Storage; `process_session`
downloads them). `wrist_l` + `wrist_r` are fused into one `wrist` payload.

## Test locally (no Firebase)

The processing core is pure Python and fully exercised on synthetic data:

```bash
pip install -e /path/to/swimlab          # the engine
cd functions && python -m pytest tests -q
```

The tests generate a synthetic swimmer → `io.write_dot_export` Custom-Mode-5 CSVs
→ `process_session`, and check the payloads + that metrics equal the direct
engine.

## Deploy / emulate

The engine must be importable in the runtime. Vendor it first (git-ignored):

```bash
cd functions
./vendor_swimlab.sh /path/to/swimlab     # copies swimlab/ + config.yaml -> vendor/
```

Set the Anthropic key as a **secret** (never in code or client):

```bash
firebase functions:secrets:set ANTHROPIC_API_KEY
```

Then, from the repo root (with `.firebaserc` pointing at your project — copy
`.firebaserc.example`):

```bash
firebase emulators:start --only functions,firestore,storage   # local
firebase deploy --only functions,firestore,storage            # live
```

## How the app calls it (Phase B)

The web/Capacitor app uses the Firebase JS SDK:

```js
import { getFunctions, httpsCallable } from "firebase/functions";
const fns = getFunctions();
const { data } = await httpsCallable(fns, "process_session")({ recordings, pool_length_m: 25 });
// data == the dashboard bundle the app already renders
const nar = await httpsCallable(fns, "narrate")({ payload, placement: "sacrum" });
```

This replaces the Cloudflare narration worker + its URL prompt: the key is a
server secret and access is gated by Firebase Auth (free vs paid enforced on the
account in Phase C).

## Notes

- **Firestore + Storage** (accounts, history, raw files) are Phase C; the Phase-A
  functions here are stateless. Rules are scaffolded in `../firestore.rules` /
  `../storage.rules`.
- `findings.py` / `narrate.py` are vendored copies of `../src/` — keep them in
  sync (same discipline as the Cloudflare worker).
- Narration currently makes two single-language calls; a follow-up switches to
  the worker's one-call EN→HE translation for lower cost.
