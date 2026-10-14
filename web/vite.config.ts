import { defineConfig } from "vite";

export default defineConfig({
  server: {
    port: 5173,
    // Proxy API calls to the FastAPI backend during development
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
