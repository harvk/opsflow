import type { FormEvent } from "react";

import { useState } from "react";

import { Link, useSearchParams } from "react-router-dom";

import FormField from "../components/forms/FormField";
import ErrorState from "../components/ui/ErrorState";
import LoadingState from "../components/ui/LoadingState";

import { useServices } from "../hooks/useServices";

import { createIncident } from "../services/serviceClient";

import { INCIDENT_SEVERITIES } from "../types/incidents";

import type {
  Incident,
  IncidentDraft,
  IncidentFormErrors,
  IncidentSeverity,
} from "../types/incidents";

import { validateIncident } from "../validation/incidentValidation";

type SubmissionState = "idle" | "submitting" | "success" | "error";

export default function ReportIncidentPage() {
  const [searchParams] = useSearchParams();

  const { requestState, retry } = useServices();

  const initialServiceId = searchParams.get("serviceId") ?? "";

  const [formValues, setFormValues] = useState<IncidentDraft>({
    serviceId: initialServiceId,
    title: "",
    severity: "Medium",
    summary: "",
    runbookUrl: "",
  });

  const [errors, setErrors] = useState<IncidentFormErrors>({});

  const [submissionState, setSubmissionState] =
    useState<SubmissionState>("idle");

  const [submissionError, setSubmissionError] = useState<string | null>(null);

  const [createdIncident, setCreatedIncident] = useState<Incident | null>(null);

  function updateField<K extends keyof IncidentDraft>(
    field: K,
    value: IncidentDraft[K],
  ) {
    setFormValues((currentValues) => ({
      ...currentValues,
      [field]: value,
    }));

    setErrors((currentErrors) => ({
      ...currentErrors,
      [field]: undefined,
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const validationErrors = validateIncident(formValues);

    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);

      return;
    }

    setErrors({});
    setSubmissionError(null);
    setSubmissionState("submitting");

    try {
      const incident = await createIncident(formValues);

      setCreatedIncident(incident);

      setSubmissionState("success");
    } catch (error) {
      setSubmissionState("error");

      setSubmissionError(
        error instanceof Error ? error.message : "Unable to create incident.",
      );
    }
  }

  if (requestState.status === "loading") {
    return <LoadingState message="Loading service options..." />;
  }

  if (requestState.status === "error") {
    return <ErrorState message={requestState.error} onRetry={retry} />;
  }

  if (submissionState === "success" && createdIncident) {
    return (
      <section className="ops-state-card">
        <p className="text-uppercase small fw-semibold text-success">
          Incident created
        </p>

        <h1 className="h3">{createdIncident.title}</h1>

        <p className="text-secondary">
          Incident <strong>{createdIncident.id}</strong> was successfully
          created.
        </p>

        <Link
          to={`/services/${createdIncident.serviceId}`}
          className="btn btn-primary"
        >
          Return to service
        </Link>
      </section>
    );
  }

  return (
    <section>
      <div className="mb-4">
        <p className="text-uppercase text-secondary fw-semibold small mb-2">
          Incident management
        </p>

        <h1 className="h2">Report incident</h1>

        <p className="text-secondary">
          Record an operational incident affecting an OpsFlow service.
        </p>
      </div>

      {submissionState === "error" && submissionError && (
        <div className="alert alert-danger" role="alert">
          {submissionError}
        </div>
      )}

      <form
        className="card border-0 shadow-sm"
        onSubmit={handleSubmit}
        noValidate
      >
        <div className="card-body p-4">
          <div className="row g-4">
            <div className="col-12 col-lg-6">
              <FormField
                id="incident-service"
                label="Affected service"
                required
                error={errors.serviceId}
              >
                <select
                  id="incident-service"
                  className={`form-select ${
                    errors.serviceId ? "is-invalid" : ""
                  }`}
                  value={formValues.serviceId}
                  aria-invalid={Boolean(errors.serviceId)}
                  aria-describedby={
                    errors.serviceId ? "incident-service-error" : undefined
                  }
                  onChange={(event) =>
                    updateField("serviceId", event.target.value)
                  }
                >
                  <option value="">Select service</option>

                  {requestState.data.map((service) => (
                    <option key={service.id} value={service.id}>
                      {service.name}
                    </option>
                  ))}
                </select>
              </FormField>
            </div>

            <div className="col-12 col-lg-6">
              <FormField id="incident-severity" label="Severity" required>
                <select
                  id="incident-severity"
                  className="form-select"
                  value={formValues.severity}
                  onChange={(event) =>
                    updateField(
                      "severity",
                      event.target.value as IncidentSeverity,
                    )
                  }
                >
                  {INCIDENT_SEVERITIES.map((severity) => (
                    <option key={severity} value={severity}>
                      {severity}
                    </option>
                  ))}
                </select>
              </FormField>
            </div>

            <div className="col-12">
              <FormField
                id="incident-title"
                label="Incident title"
                required
                error={errors.title}
                helpText="Use a concise description of the operational problem."
              >
                <input
                  id="incident-title"
                  type="text"
                  className={`form-control ${errors.title ? "is-invalid" : ""}`}
                  value={formValues.title}
                  maxLength={80}
                  aria-invalid={Boolean(errors.title)}
                  aria-describedby={
                    errors.title
                      ? "incident-title-error"
                      : "incident-title-help"
                  }
                  onChange={(event) => updateField("title", event.target.value)}
                />
              </FormField>
            </div>

            <div className="col-12">
              <FormField
                id="incident-summary"
                label="Incident summary"
                required
                error={errors.summary}
                helpText="Include symptoms, business impact, and any known triggering event."
              >
                <textarea
                  id="incident-summary"
                  className={`form-control ${
                    errors.summary ? "is-invalid" : ""
                  }`}
                  rows={6}
                  value={formValues.summary}
                  aria-invalid={Boolean(errors.summary)}
                  aria-describedby={
                    errors.summary
                      ? "incident-summary-error"
                      : "incident-summary-help"
                  }
                  onChange={(event) =>
                    updateField("summary", event.target.value)
                  }
                />
              </FormField>
            </div>

            <div className="col-12">
              <FormField
                id="incident-runbook"
                label="Runbook URL"
                error={errors.runbookUrl}
                helpText="Optional link to the operational runbook or troubleshooting documentation."
              >
                <input
                  id="incident-runbook"
                  type="url"
                  className={`form-control ${
                    errors.runbookUrl ? "is-invalid" : ""
                  }`}
                  value={formValues.runbookUrl}
                  aria-invalid={Boolean(errors.runbookUrl)}
                  aria-describedby={
                    errors.runbookUrl
                      ? "incident-runbook-error"
                      : "incident-runbook-help"
                  }
                  onChange={(event) =>
                    updateField("runbookUrl", event.target.value)
                  }
                />
              </FormField>
            </div>
          </div>
        </div>

        <div className="card-footer bg-white border-top p-4 d-flex flex-column flex-sm-row gap-2 justify-content-end">
          <Link to="/services" className="btn btn-outline-secondary">
            Cancel
          </Link>

          <button
            type="submit"
            className="btn btn-danger"
            disabled={submissionState === "submitting"}
          >
            {submissionState === "submitting"
              ? "Creating incident..."
              : "Create incident"}
          </button>
        </div>
      </form>
    </section>
  );
}
