import type { IncidentDraft, IncidentFormErrors } from "../types/incidents";

export function validateIncident(incident: IncidentDraft): IncidentFormErrors {
  const errors: IncidentFormErrors = {};

  if (!incident.serviceId) {
    errors.serviceId = "Select a service.";
  }

  const trimmedTitle = incident.title.trim();

  if (!trimmedTitle) {
    errors.title = "Enter an incident title.";
  } else if (trimmedTitle.length < 5) {
    errors.title = "The title must contain at least 5 characters.";
  } else if (trimmedTitle.length > 80) {
    errors.title = "The title must contain 80 characters or fewer.";
  }

  const trimmedSummary = incident.summary.trim();

  if (!trimmedSummary) {
    errors.summary = "Describe the incident.";
  } else if (trimmedSummary.length < 20) {
    errors.summary = "Provide at least 20 characters of incident detail.";
  }

  const runbookUrl = incident.runbookUrl.trim();

  if (runbookUrl) {
    try {
      const url = new URL(runbookUrl);

      if (url.protocol !== "http:" && url.protocol !== "https:") {
        errors.runbookUrl = "Use an HTTP or HTTPS URL.";
      }
    } catch {
      errors.runbookUrl = "Enter a valid URL.";
    }
  }

  return errors;
}
