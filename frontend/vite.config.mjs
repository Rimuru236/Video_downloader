import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [
    tailwindcss(),
    react(),
  ],
  server: {
    port: 3000,
    // Progress WebSockets live under /api/v1/ws/... (see connectProgressWS in
    // services/api.js), not a separate /ws path — so the proxy entry that
    // actually matches real traffic needs `ws: true` itself, or the dev
    // server never upgrades the connection and live progress silently never
    // connects. nginx.conf's single /api/ block already does this correctly
    // for production; this mirrors it for `npm run dev`.
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true, ws: true },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.js"],
    globals: true,
  },
});
