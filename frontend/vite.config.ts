import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The browser calls /api/*; Vite forwards to the local FastAPI server, so no CORS is needed
// and bearer tokens never leave this machine.
const proxy = {
  "/api": { target: "http://127.0.0.1:8100", rewrite: (path: string) => path.replace(/^\/api/, "") },
};

export default defineConfig({
  plugins: [react()],
  server: { host: "127.0.0.1", port: 5173, proxy },
  preview: { host: "127.0.0.1", port: 4173, proxy },
  test: { environment: "jsdom", setupFiles: ["src/test-setup.ts"] },
});
