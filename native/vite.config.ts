import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The built web assets (dist/) are what Capacitor wraps into the native app.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist" },
});
