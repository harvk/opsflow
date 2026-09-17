import { randomUUID } from "node:crypto";

export const TASK_SCHEMA_VERSION = "1.0" as const;
export const TASK_KIND = "task" as const;

export interface TaskEnvelope {
  task_id: string;
  kind: typeof TASK_KIND;
  task_type: string;
  schema_version: typeof TASK_SCHEMA_VERSION;
  created_at: string;
  producer: string;
  correlation_id: string;
  causation_id: string | null;
  idempotency_key: string;
  payload: Record<string, unknown>;
  metadata?: Record<string, string>;
}

export interface CreateTaskEnvelopeInput {
  taskType: string;
  producer: string;
  idempotencyKey: string;
  payload: Record<string, unknown>;
  correlationId?: string;
  causationId?: string | null;
  metadata?: Record<string, string>;
}

export function createTaskEnvelope(
  input: CreateTaskEnvelopeInput,
): TaskEnvelope {
  const envelope: TaskEnvelope = {
    task_id: randomUUID(),
    kind: TASK_KIND,
    task_type: input.taskType,
    schema_version: TASK_SCHEMA_VERSION,
    created_at: new Date().toISOString(),
    producer: input.producer,
    correlation_id: input.correlationId ?? randomUUID(),
    causation_id: input.causationId ?? null,
    idempotency_key: input.idempotencyKey,
    payload: input.payload,
  };

  if (input.metadata !== undefined) {
    envelope.metadata = input.metadata;
  }

  return envelope;
}
