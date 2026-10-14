import { defineConfig } from "vite";

export default defineConfig({
  server: {
    port: 5173,
    // Proxy API calls to the FastAPI backend during development
    proxy: {
      "/api": {
        // 127.0.0.1 (not localhost) — the backend binds to IPv4 only, and
        // "localhost" can resolve to IPv6 ::1 first on Windows.
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
