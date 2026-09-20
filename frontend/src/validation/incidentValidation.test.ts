import { describe, expect, it } from "vitest";

import { validateIncident } from "./incidentValidation";

describe("validateIncident", () => {
  it("returns errors for missing required values", () => {
    const errors = validateIncident({
      serviceId: "",

      title: "",

      severity: "Medium",

      summary: "",

      assignee: "",

      runbookUrl: "",
    });

    expect(errors.serviceId).toBeDefined();

    expect(errors.title).toBeDefined();

    expect(errors.summary).toBeDefined();

    expect(errors.assignee).toBeDefined();
  });

  it("accepts a valid incident", () => {
    const errors = validateIncident({
      serviceId: "604ee093-cafc-42a9-b224-d91d6c1f5680",

      title: "Order API latency elevated",

      severity: "High",

      summary:
        "Order processing latency is significantly " +
        "above the normal operational baseline.",

      assignee: "Platform Operations",

      runbookUrl: "https://example.com/runbook",
    });

    expect(errors).toEqual({});
  });

  it("accepts an empty optional runbook URL", () => {
    const errors = validateIncident({
      serviceId: "604ee093-cafc-42a9-b224-d91d6c1f5680",

      title: "Order API latency elevated",

      severity: "High",

      summary:
        "Order processing latency is significantly " +
        "above the normal operational baseline.",

      assignee: "Platform Operations",

      runbookUrl: "",
    });

    expect(errors.runbookUrl).toBeUndefined();
  });

  it("accepts an HTTP runbook URL", () => {
    const errors = validateIncident({
      serviceId: "604ee093-cafc-42a9-b224-d91d6c1f5680",

      title: "Order API latency elevated",

      severity: "High",

      summary:
        "Order processing latency is significantly " +
        "above the normal operational baseline.",

      assignee: "Platform Operations",

      runbookUrl: "http://example.com/runbook",
    });

    expect(errors.runbookUrl).toBeUndefined();
  });

  it("rejects a runbook URL without HTTP or HTTPS", () => {
    const errors = validateIncident({
      serviceId: "604ee093-cafc-42a9-b224-d91d6c1f5680",

      title: "Order API latency elevated",

      severity: "High",

      summary:
        "Order processing latency is significantly " +
        "above the normal operational baseline.",

      assignee: "Platform Operations",

      runbookUrl: "example.com/runbook",
    });

    expect(errors.runbookUrl).toBe("Use an HTTP or HTTPS URL.");
  });

  it("rejects spaces inside a runbook URL", () => {
    const errors = validateIncident({
      serviceId: "604ee093-cafc-42a9-b224-d91d6c1f5680",

      title: "Order API latency elevated",

      severity: "High",

      summary:
        "Order processing latency is significantly " +
        "above the normal operational baseline.",

      assignee: "Platform Operations",

      runbookUrl: "https://example.com/my runbook",
    });

    expect(errors.runbookUrl).toBe("Enter a valid URL.");
  });

  it("rejects leading whitespace in a runbook URL", () => {
    const errors = validateIncident({
      serviceId: "604ee093-cafc-42a9-b224-d91d6c1f5680",

      title: "Order API latency elevated",

      severity: "High",

      summary:
        "Order processing latency is significantly " +
        "above the normal operational baseline.",

      assignee: "Platform Operations",

      runbookUrl: " https://example.com/runbook",
    });

    expect(errors.runbookUrl).toBe("Use an HTTP or HTTPS URL.");
  });

  it("rejects trailing whitespace in a runbook URL", () => {
    const errors = validateIncident({
      serviceId: "604ee093-cafc-42a9-b224-d91d6c1f5680",

      title: "Order API latency elevated",

      severity: "High",

      summary:
        "Order processing latency is significantly " +
        "above the normal operational baseline.",

      assignee: "Platform Operations",

      runbookUrl: "https://example.com/runbook ",
    });

    expect(errors.runbookUrl).toBe("Enter a valid URL.");
  });
});
