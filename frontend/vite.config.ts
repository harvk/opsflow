import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  // ========================================================
  // REACT
  // ========================================================
  //
  // Enables React Fast Refresh and the normal React/Vite
  // transformation pipeline.
  //
  // ========================================================

  plugins: [react()],

  // ========================================================
  // VITE DEVELOPMENT SERVER
  // ========================================================
  //
  // The frontend source directory is bind-mounted from the
  // Windows host into the Linux Docker container:
  //
  //     ./frontend
  //          |
  //          v
  //       /app
  //
  // Docker Desktop on Windows does not always propagate
  // native filesystem notification events reliably across
  // this boundary.
  //
  // Polling causes Vite to periodically inspect the mounted
  // files for changes instead of depending entirely on
  // native filesystem events.
  //
  // This allows HMR / React Fast Refresh to work when source
  // files are edited from VS Code on the Windows host.
  //
  // ========================================================

  server: {
    watch: {
      usePolling: true,
      interval: 250,
    },
  },

  // ========================================================
  // VITEST
  // ========================================================

  test: {
    environment: "jsdom",

    setupFiles: "./src/test/setup.ts",

    globals: true,

    css: true,
  },
});
