import Ajv2020, {
  type AnySchema,
  type ErrorObject,
  type ValidateFunction,
} from "ajv/dist/2020.js";

import addFormats from "ajv-formats";

import incidentUpdatedSchema from "../../../contracts/notifications/incident-updated-v1.schema.json";

import type { RealtimeIncidentMessage } from "./types";

const ajv = new Ajv2020({
  allErrors: true,

  strict: true,
});

addFormats(ajv);

const validateNotification: ValidateFunction<RealtimeIncidentMessage> =
  ajv.compile<RealtimeIncidentMessage>(incidentUpdatedSchema as AnySchema);

function formatValidationErrors(errors: readonly ErrorObject[]): string {
  if (errors.length === 0) {
    return "unknown contract violation";
  }

  return errors
    .map((error) => {
      const path = error.instancePath.length > 0 ? error.instancePath : "/";

      const message = error.message ?? "is invalid";

      return `${path} ${message}`;
    })
    .join("; ");
}

export class InvalidRealtimeNotificationError extends Error {
  readonly validationErrors: readonly ErrorObject[];

  constructor(validationErrors: readonly ErrorObject[]) {
    super(
      "incident.updated notification failed " +
        "v1 contract validation: " +
        formatValidationErrors(validationErrors),
    );

    this.name = "InvalidRealtimeNotificationError";

    this.validationErrors = validationErrors;
  }
}

export function validateRealtimeIncidentMessage(
  value: unknown,
): RealtimeIncidentMessage {
  if (validateNotification(value)) {
    return value;
  }

  const validationErrors = [...(validateNotification.errors ?? [])];

  throw new InvalidRealtimeNotificationError(validationErrors);
}
