# swimlab — native app (Capacitor + React)

Phase 2/D of the product (see `../docs/app-architecture.md`): the per-placement
dashboards as a real iOS/Android app, talking to the **same deployed backend**
as the web app (`process_session` / `narrate`), with accounts, history, and a
Movella DOT BLE capture path.

This is a **scaffold** — a working web build (`npm run dev`) you can run today,
plus the native wrappers a `cap add` away. The BLE transport is a documented
skeleton; everything else (auth, processing, dashboards with playback, narration,
history, save-to-account) works against the live functions.

## Layout

```
native/
  index.html, vite.config.ts, capacitor.config.ts, tsconfig.json
  src/
    main.tsx, App.tsx, styles.css
    lib/firebase.ts      Firebase init from Vite env (.env)
    lib/backend.ts       process_session / narrate callables + history/bundle reads
    lib/i18n.ts          EN/HE strings (Hebrew default, RTL)
    App.tsx              shell: splash -> onboarding -> auth -> tabbed nav
    components/
      Splash / Onboarding / BottomNav   launch + first-run + Home/Capture/History/Settings nav
      Home / Capture / Settings         screens (Home hosts the dashboards)
      ImportWizard.tsx   multi-DOT capture: add sensors (single file, or
                         trial + 2 calibration), tag placement, then process
      AuthGate.tsx       Google + Email/Password sign-in
      Dashboard.tsx      banner + labelled KPIs + trace chart + playback +
                         default rule-based findings/coaching + AI narrate
      Findings.tsx       the bilingual rule-based analysis (no AI call)
      Drills.tsx         per-placement drills library + YouTube video modal
      MotionSchematic    canvas figure (head/body/arms) animated by the playhead
      PlaybackControls   play / pause / speed (0.5–4×) / scrub
      TraceChart.tsx     canvas traces with a playhead
      History.tsx        saved swims -> reload a bundle from Storage
    ble/dot.ts           Movella DOT Custom-Mode-5 decode + CSV assemble (solid);
                         BLE scan/connect/notify skeleton (TODO real device);
                         MockDotSensor + file import for synthetic data
```

## Run it (web preview)

```bash
cd native
npm install
cp .env.example .env          # paste your Firebase web config
npm run dev                   # http://localhost:5173
```

Sign in, then **Import recordings** — feed the synthetic Custom-Mode-5 CSVs from
`../functions/tools/make_sample_recordings.py` (or a `request.json`). It runs
through `process_session`, renders the placement dashboards with playback, saves
to your account, and **Narrate** calls the server. Everything mirrors the web app.

## Wrap as a native app

```bash
npm run build                 # tsc + vite -> dist/
npx cap add ios               # and/or: npx cap add android
npx cap sync
npx cap open ios              # build/run in Xcode / Android Studio
```

For BLE on device, add the platform permissions after `cap add`:

- **iOS** `ios/App/App/Info.plist`: `NSBluetoothAlwaysUsageDescription`.
- **Android** `AndroidManifest.xml`: `BLUETOOTH_SCAN`, `BLUETOOTH_CONNECT`
  (and location on older APIs).

## Capture: what's real vs TODO

- **Solid:** `decodeCustomMode5()` / `assembleCustomMode5Csv()` in `ble/dot.ts`
  — the byte layout and the canonical CSV columns the backend reads, derived in
  `swimlab/io.py` from the `jiminghe/Xsens_DOT_PC_Reader` reference parser.
- **TODO(real-device):** the GATT UUIDs, the measurement-control bytes to select
  Custom Mode 5, and the notification framing in `BleDotSensor`. Validate against
  a real DOT, then flip capture from the import/mock path to live BLE. Note DOT
  BLE drops underwater and streams at ≤60 Hz — the intended path is **onboard
  120 Hz recording + offload after the swim**, which a later revision wires in
  place of live streaming.

## Next

- Presentation parity with the web dashboards (drills + video modals, motion
  schematics) — port from `../src/app_template.html`.
- RevenueCat billing for the paid tier (narration + progress analysis).
- Onboard-file offload for real underwater capture.
