import type { IncidentDraft, IncidentFormErrors } from "../types/incidents";

const RUNBOOK_URL_PATTERN = /^https?:\/\/\S+$/;

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

  const trimmedAssignee = incident.assignee.trim();

  if (!trimmedAssignee) {
    errors.assignee = "Enter an assignee.";
  } else if (trimmedAssignee.length > 120) {
    errors.assignee = "The assignee must contain 120 characters or fewer.";
  }

  const runbookUrl = incident.runbookUrl;

  if (runbookUrl && !RUNBOOK_URL_PATTERN.test(runbookUrl)) {
    if (
      !runbookUrl.startsWith("http://") &&
      !runbookUrl.startsWith("https://")
    ) {
      errors.runbookUrl = "Use an HTTP or HTTPS URL.";
    } else {
      errors.runbookUrl = "Enter a valid URL.";
    }
  }

  return errors;
}
