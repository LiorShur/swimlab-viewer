import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "app.swimlab",
  appName: "swimlab",
  webDir: "dist",
  server: { androidScheme: "https" },
  plugins: {
    // Movella DOT advertises under the "Xsens DOT"/"Movella DOT" name; BLE
    // permissions are declared in the native projects after `cap add`.
    BluetoothLe: { displayStrings: {} },
  },
};

export default config;
