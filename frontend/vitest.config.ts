import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    /*
     * React components execute in a browser-like DOM
     * environment rather than Node's server-only
     * environment.
     *
     * This also gives API tests browser primitives such as:
     *
     *   window
     *   document
     *   Headers
     *   Response
     *   URL
     */
    environment: "jsdom",

    /*
     * Run this file before every test suite.
     *
     * It installs the Testing Library / jest-dom
     * assertions that will be used heavily when we begin
     * component testing.
     */
    setupFiles: ["./src/test/setup.ts"],

    /*
     * These options keep individual tests isolated from
     * one another.
     *
     * Authentication tests are particularly sensitive to
     * leaked mocks because many of them replace fetch().
     */
    clearMocks: true,

    mockReset: true,

    restoreMocks: true,
  },
});
