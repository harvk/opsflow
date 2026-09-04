import { describe, expect, it } from "vitest";

import { validateIncident } from "./incidentValidation";

describe("validateIncident", () => {
  it("returns errors for missing required values", () => {
    const errors = validateIncident({
      serviceId: "",
      title: "",
      severity: "Medium",
      summary: "",
      runbookUrl: "",
    });

    expect(errors.serviceId).toBeDefined();

    expect(errors.title).toBeDefined();

    expect(errors.summary).toBeDefined();
  });

  it("accepts a valid incident", () => {
    const errors = validateIncident({
      serviceId: "order-api",

      title: "Order API latency elevated",

      severity: "High",

      summary:
        "Order processing latency is significantly above the normal operational baseline.",

      runbookUrl: "https://example.com/runbook",
    });

    expect(errors).toEqual({});
  });
});
