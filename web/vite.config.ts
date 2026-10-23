import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The UI never talks to Moomoo or holds secrets. /api is proxied to the local
// Python API (same origin from the browser's view, so no CORS is configured).
const api = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: { host: "127.0.0.1", port: 5173, proxy: { "/api": api } },
  preview: { host: "127.0.0.1", port: 5173, proxy: { "/api": api } },
});
