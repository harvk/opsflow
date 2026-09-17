import { describe, expect, it } from "vitest";

import { createTaskEnvelope } from "../src/taskEnvelope";

describe("createTaskEnvelope", () => {
  it("creates the required v1 task fields", () => {
    const envelope = createTaskEnvelope({
      taskType: "incident.notification.requested",
      producer: "opsflow-task-publisher",
      idempotencyKey: "incident:123:notification:opened",
      payload: {
        incident_id: 123,
      },
    });

    expect(envelope.kind).toBe("task");
    expect(envelope.schema_version).toBe("1.0");

    expect(envelope.task_type).toBe("incident.notification.requested");

    expect(envelope.producer).toBe("opsflow-task-publisher");

    expect(envelope.idempotency_key).toBe("incident:123:notification:opened");

    expect(envelope.task_id).toMatch(/^[0-9a-f-]{36}$/i);

    expect(envelope.correlation_id).toMatch(/^[0-9a-f-]{36}$/i);

    expect(envelope.causation_id).toBeNull();

    expect(Number.isNaN(Date.parse(envelope.created_at))).toBe(false);
  });

  it("preserves caller-provided tracing identifiers", () => {
    const correlationId = "40e6215d-b5c6-4896-987c-f30f3678f608";

    const causationId = "6a055370-9341-4ff5-89b2-a6fcae1e238c";

    const envelope = createTaskEnvelope({
      taskType: "incident.notification.requested",
      producer: "opsflow-task-publisher",
      idempotencyKey: "incident:123:notification:opened",
      payload: {
        incident_id: 123,
      },
      correlationId,
      causationId,
    });

    expect(envelope.correlation_id).toBe(correlationId);

    expect(envelope.causation_id).toBe(causationId);
  });

  it("omits metadata when metadata is not supplied", () => {
    const envelope = createTaskEnvelope({
      taskType: "service.healthcheck.requested",
      producer: "opsflow-task-publisher",
      idempotencyKey: "service:42:healthcheck:001",
      payload: {
        service_id: 42,
      },
    });

    expect(envelope.metadata).toBeUndefined();
  });
});
