/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// RegRails web SPA. base "/" + build to dist/ (Vercel serves dist/ statically;
// the api/*.py serverless functions are deployed alongside, untouched by Vite).
export default defineConfig({
  base: "/",
  plugins: [react()],
  build: {
    outDir: "dist",
    // Don't ship original TS source maps to the public demo (security L-4).
    sourcemap: false,
  },
  server: {
    port: 5173,
  },
  preview: {
    port: 4173,
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // Playwright specs live in tests/ and use @playwright/test, not vitest.
    exclude: ["tests/**", "node_modules/**", "dist/**"],
    css: false,
  },
});
