import Ajv2020, {
  type ErrorObject,
  type ValidateFunction,
} from "ajv/dist/2020.js";

import addFormats from "ajv-formats";

import incidentUpdatedSchema from "../../../contracts/notifications/incident-updated-v1.schema.json";

import type { IncidentUpdatedNotification } from "./types";

const ajv = new Ajv2020({
  allErrors: true,

  strict: true,
});

addFormats(ajv);

const validateNotification: ValidateFunction<IncidentUpdatedNotification> =
  ajv.compile<IncidentUpdatedNotification>(incidentUpdatedSchema);

function formatValidationErrors(errors: readonly ErrorObject[]): string {
  if (errors.length === 0) {
    return "unknown notification " + "contract violation";
  }

  return errors
    .map((error) => {
      const path = error.instancePath.length > 0 ? error.instancePath : "/";

      const message = error.message ?? "is invalid";

      return `${path} ${message}`;
    })
    .join("; ");
}

export class InvalidWebhookNotificationError extends Error {
  readonly validationErrors: readonly ErrorObject[];

  constructor(validationErrors: readonly ErrorObject[]) {
    super(
      "incident.updated webhook " +
        "notification failed v1 " +
        "contract validation: " +
        formatValidationErrors(validationErrors),
    );

    this.name = "InvalidWebhookNotificationError";

    this.validationErrors = [...validationErrors];
  }
}

export function validateWebhookNotification(
  value: unknown,
): IncidentUpdatedNotification {
  if (validateNotification(value)) {
    return value;
  }

  throw new InvalidWebhookNotificationError([
    ...(validateNotification.errors ?? []),
  ]);
}
