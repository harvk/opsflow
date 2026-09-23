import { Link, useParams } from "react-router-dom";

import type { ServiceStatus } from "../types/dashboard";

import ErrorState from "../components/ui/ErrorState";
import LoadingState from "../components/ui/LoadingState";
import StatusBadge from "../components/StatusBadge";
import ServiceIncidentHistory from "../components/ServiceIncidentHistory";

import { useServiceDetails } from "../hooks/useServiceDetails";
import { useServiceIncidents } from "../hooks/useServiceIncidents";

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

const SERVICE_STATUS_TONE_CLASS: Record<ServiceStatus, string> = {
  Healthy: "healthy",
  Degraded: "degraded",
  Critical: "critical",
};

export default function ServiceDetailsPage() {
  const { serviceId } = useParams<{
    serviceId: string;
  }>();

  const requestState = useServiceDetails(serviceId);
  const incidentsState = useServiceIncidents(serviceId);

  if (requestState.status === "loading") {
    return <LoadingState message="Loading service details..." />;
  }

  if (requestState.status === "error") {
    return <ErrorState message={requestState.error} />;
  }

  if (requestState.data === null) {
    return (
      <section className="ops-state-card text-center">
        <h1 className="h3">Service not found</h1>

        <p className="text-secondary">The requested service does not exist.</p>

        <Link to="/services" className="btn btn-primary">
          Return to services
        </Link>
      </section>
    );
  }

  const service = requestState.data;
  const serviceStatusTone = SERVICE_STATUS_TONE_CLASS[service.status];

  return (
    <article>
      <div className="d-flex flex-column flex-lg-row justify-content-between gap-3 mb-4">
        <div>
          <Link
            to="/services"
            className="small text-decoration-none service-details-actions"
          >
            ← Back to services
          </Link>

          <div className="d-flex flex-wrap align-items-center gap-3 mt-3">
            <h1 className="h2 mb-0">{service.name}</h1>

            <StatusBadge status={service.status} />
          </div>

          <p className="text-secondary mt-2 mb-0">{service.description}</p>
        </div>

        <div className="align-self-lg-start">
          <Link
            to={`/incidents/new?serviceId=${encodeURIComponent(service.id)}`}
            className="btn btn-danger"
          >
            Report incident
          </Link>
        </div>
      </div>

      <div className="row g-4 mb-4">
        <div className="col-12 col-sm-6 col-xl-3">
          <div
            className={`card border-0 shadow-sm h-100 ops-service-fact-card ops-service-fact-card--${serviceStatusTone}`}
          >
            <div className="card-body">
              <p className="small text-secondary mb-1">Owner</p>

              <p className="fw-semibold mb-0">{service.owner}</p>
            </div>
          </div>
        </div>

        <div className="col-12 col-sm-6 col-xl-3">
          <div
            className={`card border-0 shadow-sm h-100 ops-service-fact-card ops-service-fact-card--${serviceStatusTone}`}
          >
            <div className="card-body">
              <p className="small text-secondary mb-1">Region</p>

              <p className="fw-semibold mb-0">{service.region}</p>
            </div>
          </div>
        </div>

        <div className="col-12 col-sm-6 col-xl-3">
          <div
            className={`card border-0 shadow-sm h-100 ops-service-fact-card ops-service-fact-card--${serviceStatusTone}`}
          >
            <div className="card-body">
              <p className="small text-secondary mb-1">Version</p>

              <p className="fw-semibold mb-0">{service.version}</p>
            </div>
          </div>
        </div>

        <div className="col-12 col-sm-6 col-xl-3">
          <div
            className={`card border-0 shadow-sm h-100 ops-service-fact-card ops-service-fact-card--${serviceStatusTone}`}
          >
            <div className="card-body">
              <p className="small text-secondary mb-1">Latency</p>

              <p className="fw-semibold mb-0">{service.latencyMs} ms</p>
            </div>
          </div>
        </div>
      </div>

      <section
        className="card border-0 shadow-sm"
        aria-labelledby="service-runtime-heading"
      >
        <div className="card-body p-4">
          <h2 id="service-runtime-heading" className="h5">
            Runtime information
          </h2>

          <dl className="row mb-0">
            <dt className="col-sm-4">Uptime</dt>

            <dd className="col-sm-8">{service.uptime}</dd>

            <dt className="col-sm-4">Last deployment</dt>

            <dd className="col-sm-8">
              <time dateTime={service.lastDeployedAt}>
                {formatDateTime(service.lastDeployedAt)}
              </time>
            </dd>

            <dt className="col-sm-4">Dependencies</dt>

            <dd className="col-sm-8">
              {service.dependencies.length > 0
                ? service.dependencies.join(", ")
                : "None"}
            </dd>
          </dl>
        </div>
      </section>

      <div className="mt-4">
        {incidentsState.status === "loading" ? (
          <section
            className="card border-0 shadow-sm"
            aria-live="polite"
            aria-busy="true"
          >
            <div className="card-body p-4 p-lg-5">
              <div className="d-flex align-items-center gap-3">
                <div
                  className="spinner-border spinner-border-sm text-primary"
                  role="status"
                >
                  <span className="visually-hidden">
                    Loading reported incidents
                  </span>
                </div>

                <span className="text-secondary">
                  Loading reported incidents…
                </span>
              </div>
            </div>
          </section>
        ) : null}

        {incidentsState.status === "error" ? (
          <section className="card border-0 shadow-sm">
            <div className="card-body p-4 p-lg-5">
              <h2 className="h5">Reported incidents unavailable</h2>
              <p className="text-secondary mb-0">{incidentsState.error}</p>
            </div>
          </section>
        ) : null}

        {incidentsState.status === "success" ? (
          <ServiceIncidentHistory incidents={incidentsState.data} />
        ) : null}
      </div>
    </article>
  );
}
