import { describe, expect, it } from "vitest";

import validTask from "../../contracts/tasks/fixtures/valid-task-v1.json";

import invalidTask from "../../contracts/tasks/fixtures/invalid-task-missing-idempotency-v1.json";

import { validateTaskEnvelope } from "../src/validation";

describe("task envelope validation", () => {
  it("accepts the canonical valid Phase 11.1 fixture", () => {
    const result = validateTaskEnvelope(validTask);

    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });

  it("rejects a task without idempotency_key", () => {
    const result = validateTaskEnvelope(invalidTask);

    expect(result.valid).toBe(false);

    expect(
      result.errors.some(
        (error) =>
          error.keyword === "required" &&
          error.params.missingProperty === "idempotency_key",
      ),
    ).toBe(true);
  });

  it("rejects additional envelope properties", () => {
    const result = validateTaskEnvelope({
      ...validTask,
      unauthorized_field: "should-fail",
    });

    expect(result.valid).toBe(false);

    expect(
      result.errors.some((error) => error.keyword === "additionalProperties"),
    ).toBe(true);
  });
});
