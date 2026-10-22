import { defineConfig } from "vite";
import { execSync } from "node:child_process";

// Build identity: the commit this frontend was built (or served) from, so the
// UI can warn when it doesn't match the commit the backend loaded. 7 chars to
// match the server's BUILD_INFO["short"] exactly.
function gitShortCommit(): string {
  try {
    return execSync("git rev-parse HEAD", { stdio: ["ignore", "pipe", "ignore"] })
      .toString().trim().slice(0, 7) || "unknown";
  } catch {
    return "unknown";
  }
}

export default defineConfig({
  define: {
    __WEB_COMMIT__: JSON.stringify(gitShortCommit()),
    __WEB_BUILT_AT__: JSON.stringify(new Date().toISOString()),
  },
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
