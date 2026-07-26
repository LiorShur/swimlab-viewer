# Live narration proxy (Cloudflare Worker)

GitHub Pages is static, so it can't hold your Anthropic API key without leaking
it to anyone who opens the page. This tiny Worker holds the key **server-side**,
accepts a session's already-computed metrics, calls Claude, and returns the same
`{summary, corrections, drills, model}` narrative that `src/narrate.py` produces
offline. The static dashboard `fetch()`es it on demand — the key never reaches
the browser.

The deterministic pipeline (calibrate → events → metrics → stats) is **not** in
the loop here. As with `--narrate`, Claude only rewrites the interpretation
prose, from a fixed fact table. `narrate-worker.js` is a straight port of
`src/narrate.py`; keep the two in sync.

## Deploy

```bash
cd worker
npx wrangler login                      # once
npx wrangler secret put ANTHROPIC_API_KEY   # paste your key when prompted
npx wrangler deploy                     # prints https://swimlab-narrate.<you>.workers.dev
```

Edit `wrangler.toml` first and set `ALLOWED_ORIGIN` to your Pages origin, e.g.
`https://liorshur.github.io`. That makes browsers on other sites unable to call
your Worker. (It does not stop a hand-rolled `curl` — see Cost & abuse below.)

## Point the page at it

The dashboard resolves the Worker URL in this order:

1. `window.SWIMLAB_NARRATE_URL` (define it in an inline `<script>` if you host
   your own copy)
2. `?narrate=<url>` query param — saved to `localStorage` on first use
3. `localStorage["swimlab.narrateUrl"]`
4. otherwise it `prompt()`s once and remembers your answer

So the quickest test is to open:

```
https://liorshur.github.io/swimlab-viewer/dashboard.html?narrate=https://swimlab-narrate.<you>.workers.dev
```

Then click **✨ Narrate live** — it narrates whichever swimmer is selected (or a
session you just imported) and swaps in Claude's text under an "AI-generated"
badge.

## Language (English / Hebrew)

The page has an EN/HE toggle (🌐). Static UI, the rule-based fallback text, and
the live AI narration all follow it — the page sends `{lang: "he"}` in the
request body and the Worker instructs Claude to write the prose in Hebrew (only
the prose changes; the metric citations and numbers stay as computed). Narratives
are cached per language, so switching languages shows the right one without a
re-call. The default is Hebrew; the choice persists in `localStorage`.

To bake Hebrew narratives offline instead of calling live, pass `--lang he`:

```bash
python src/export_session.py --set --narrate --lang he --out sessions.json
```

## Optional shared secret

For a bit of extra friction, set a secret and the Worker will require a matching
header:

```bash
npx wrangler secret put SHARED_SECRET
```

Pass it to the page with `?narrateKey=<secret>` (also saved to `localStorage`,
sent as `X-Narrate-Key`). Note: on a fully public page the secret ends up in the
browser, so treat it as friction, not real auth.

## Cost & abuse

`ALLOWED_ORIGIN` blocks cross-site browser calls, but anyone who finds the URL
can still `curl` it and spend your tokens. Real protection for a public prototype:

- **`max_tokens` is capped at 2000 per call** in the Worker, bounding per-request cost.
- Add a **Cloudflare rate-limiting rule** on the Worker route (dashboard →
  Security → WAF → Rate limiting) — e.g. 20 requests / minute / IP. No code needed.
- Keep the Worker URL out of public READMEs if you want it semi-private, and use
  the shared secret above.

## Staying pre-baked instead

You don't need this Worker at all if you're happy baking narratives offline:

```bash
python src/export_session.py --set --narrate --out sessions.json
python src/build.py --data sessions.json --out dashboard.html
```

That commits Claude's text as static content — free, zero infra. The Worker is
only for on-demand "import a file → narrate it live" without a rebuild.
