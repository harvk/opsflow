import { describe, expect, it } from "vitest";

import {
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
  PASSWORD_TOO_LONG_MESSAGE,
  PASSWORD_TOO_SHORT_MESSAGE,
  evaluatePasswordLength,
} from "./passwordPolicy";

/*
 * =========================================================
 * CONSTANT CONTRACT
 * =========================================================
 */

describe("frontend password policy constants", () => {
  it("uses the expected minimum length", () => {
    expect(PASSWORD_MIN_LENGTH).toBe(15);
  });

  it("uses the expected maximum length", () => {
    expect(PASSWORD_MAX_LENGTH).toBe(128);
  });

  it("builds the minimum-length message from the shared constant", () => {
    expect(PASSWORD_TOO_SHORT_MESSAGE).toBe(
      "Your new password must contain " + "at least 15 characters.",
    );
  });

  it("builds the maximum-length message from the shared constant", () => {
    expect(PASSWORD_TOO_LONG_MESSAGE).toBe(
      "Your new password must not exceed " + "128 characters.",
    );
  });
});

/*
 * =========================================================
 * LOWER BOUNDARY
 * =========================================================
 */

describe("frontend password policy minimum boundary", () => {
  it("rejects one character below the minimum", () => {
    const result = evaluatePasswordLength("a".repeat(PASSWORD_MIN_LENGTH - 1));

    expect(result.length).toBe(PASSWORD_MIN_LENGTH - 1);

    expect(result.meetsMinimumLength).toBe(false);

    expect(result.withinMaximumLength).toBe(true);

    expect(result.isValid).toBe(false);
  });

  it("accepts the exact minimum", () => {
    const result = evaluatePasswordLength("a".repeat(PASSWORD_MIN_LENGTH));

    expect(result.meetsMinimumLength).toBe(true);

    expect(result.withinMaximumLength).toBe(true);

    expect(result.isValid).toBe(true);
  });
});

/*
 * =========================================================
 * UPPER BOUNDARY
 * =========================================================
 */

describe("frontend password policy maximum boundary", () => {
  it("accepts the exact maximum", () => {
    const result = evaluatePasswordLength("a".repeat(PASSWORD_MAX_LENGTH));

    expect(result.meetsMinimumLength).toBe(true);

    expect(result.withinMaximumLength).toBe(true);

    expect(result.isValid).toBe(true);
  });

  it("rejects one character above the maximum", () => {
    const result = evaluatePasswordLength("a".repeat(PASSWORD_MAX_LENGTH + 1));

    expect(result.meetsMinimumLength).toBe(true);

    expect(result.withinMaximumLength).toBe(false);

    expect(result.isValid).toBe(false);
  });
});

/*
 * =========================================================
 * PROGRESS PRESENTATION
 * =========================================================
 */

describe("frontend password policy progress", () => {
  it("starts at zero percent", () => {
    const result = evaluatePasswordLength("");

    expect(result.progressPercent).toBe(0);
  });

  it("reaches one hundred percent at the minimum", () => {
    const result = evaluatePasswordLength("a".repeat(PASSWORD_MIN_LENGTH));

    expect(result.progressPercent).toBe(100);
  });

  it("does not exceed one hundred percent", () => {
    const result = evaluatePasswordLength("a".repeat(PASSWORD_MAX_LENGTH));

    expect(result.progressPercent).toBe(100);
  });
});
