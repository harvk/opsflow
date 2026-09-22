import Ajv2020, {
  type AnySchema,
  type ErrorObject,
  type ValidateFunction,
} from "ajv/dist/2020.js";

import addFormats from "ajv-formats";

import taskEnvelopeSchema from "../../contracts/tasks/task-envelope-v1.schema.json";

const ajv = new Ajv2020({
  allErrors: true,
  strict: true,
});

addFormats(ajv);

const validate = ajv.compile(
  taskEnvelopeSchema as AnySchema,
) as ValidateFunction<unknown>;

export interface TaskEnvelopeValidationResult {
  valid: boolean;
  errors: ErrorObject[];
}

export class InvalidTaskEnvelopeError extends Error {
  readonly validationErrors: ErrorObject[];

  constructor(validationErrors: ErrorObject[]) {
    super("Task envelope does not satisfy the v1 contract");

    this.name = "InvalidTaskEnvelopeError";
    this.validationErrors = validationErrors;
  }
}

export function validateTaskEnvelope(
  value: unknown,
): TaskEnvelopeValidationResult {
  const valid = validate(value);

  return {
    valid,
    errors: validate.errors ? [...validate.errors] : [],
  };
}

export function assertValidTaskEnvelope(value: unknown): void {
  const result = validateTaskEnvelope(value);

  if (!result.valid) {
    throw new InvalidTaskEnvelopeError(result.errors);
  }
}
