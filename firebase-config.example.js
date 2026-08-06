/* Firebase web config for the hosted swimlab app (Phase B).
 *
 * Copy this file to `firebase-config.js` (git-ignored) and paste your project's
 * web config from the Firebase console:
 *   Project Settings -> General -> Your apps -> Web app -> "SDK setup and config".
 *
 * The hosted app loads `/firebase-config.js` before boot; when present it wires
 * `window.SwimBackend` to the deployed `process_session` / `narrate` callables,
 * so narration and raw-DOT processing run server-side with no worker URL and no
 * client-side API key. When absent (e.g. the offline dashboard artifacts), the
 * app silently falls back to the Cloudflare worker / rule-based findings.
 */
window.SWIMLAB_FIREBASE_CONFIG = {
  apiKey: "YOUR_WEB_API_KEY",
  authDomain: "your-project-id.firebaseapp.com",
  projectId: "your-project-id",
  storageBucket: "your-project-id.appspot.com",
  messagingSenderId: "0000000000",
  appId: "1:0000000000:web:xxxxxxxxxxxxxxxx",
  // Optional: override if you deployed the functions to a non-default region.
  functionsRegion: "us-central1",
};

// Optional: pin the Firebase JS SDK version the app imports from gstatic.
// window.SWIMLAB_FIREBASE_SDK_VERSION = "10.12.0";

// Optional (local dev): route callables at the Functions emulator instead of prod.
// window.SWIMLAB_FUNCTIONS_EMULATOR = "localhost:5001";
