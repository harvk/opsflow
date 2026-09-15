import { useEffect, useState } from "react";

import MetricCard from "../components/MetricCard";
import RecentActivity from "../components/RecentActivity";
import ServiceHealthSummary from "../components/ServiceHealthSummary";

import { getOverview, OverviewRequestError } from "../services/overviewClient";

import type {
  OverviewIncident,
  OverviewResponse,
  OverviewSummary,
} from "../services/overviewClient";

import type { ActivityItem, AsyncState, Metric } from "../types/dashboard";

/*
 * =========================================================
 * ASYNC STATE
 * =========================================================
 */

const INITIAL_OVERVIEW_STATE: AsyncState<OverviewResponse> = {
  status: "loading",

  data: null,

  error: null,
};

/*
 * =========================================================
 * SUMMARY TO METRIC MAPPING
 * =========================================================
 */

function buildDashboardMetrics(
  summary: OverviewSummary,
  incidentDataAvailable: boolean,
): Metric[] {
  const activeIncidents = summary.activeIncidents;

  const customerImpactingIncidents = summary.customerImpactingIncidents;

  const hasIncidentData =
    incidentDataAvailable &&
    activeIncidents !== null &&
    customerImpactingIncidents !== null;

  const serviceHealthAccent: Metric["accent"] =
    summary.criticalServices > 0
      ? "danger"
      : summary.degradedServices > 0
        ? "warning"
        : "success";

  const incidentAccent: Metric["accent"] = !hasIncidentData
    ? "warning"
    : (activeIncidents ?? 0) > 0
      ? "danger"
      : "success";

  const customerImpactAccent: Metric["accent"] = !hasIncidentData
    ? "warning"
    : (customerImpactingIncidents ?? 0) > 0
      ? "danger"
      : "primary";

  return [
    {
      id: "total-services",

      label: "Services monitored",

      value: String(summary.totalServices),

      supportingText:
        `${summary.degradedServices} degraded and ` +
        `${summary.criticalServices} critical`,

      accent: serviceHealthAccent,
    },
    {
      id: "healthy-services",

      label: "Healthy services",

      value: String(summary.healthyServices),

      supportingText:
        `${summary.healthyServices} of ` +
        `${summary.totalServices} reporting healthy`,

      accent: "success",
    },
    {
      id: "active-incidents",

      label: "Active incidents",

      value: hasIncidentData ? String(activeIncidents) : "Unavailable",

      supportingText: !hasIncidentData
        ? "Incident Management data is temporarily unavailable"
        : activeIncidents === 0
          ? "No active incidents"
          : "Open, investigating, or monitoring",

      accent: incidentAccent,
    },
    {
      id: "customer-impacting-incidents",

      label: "Customer-impacting",

      value: hasIncidentData
        ? String(customerImpactingIncidents)
        : "Unavailable",

      supportingText: !hasIncidentData
        ? "Customer-impact status cannot currently be verified"
        : customerImpactingIncidents === 0
          ? "No active customer impact"
          : "Active incidents affecting customers",

      accent: customerImpactAccent,
    },
  ];
}

/*
 * =========================================================
 * INCIDENT TO ACTIVITY MAPPING
 * =========================================================
 */

function buildRecentActivity(incidents: OverviewIncident[]): ActivityItem[] {
  return [...incidents]
    .sort(
      (left, right) => Date.parse(right.updatedAt) - Date.parse(left.updatedAt),
    )
    .slice(0, 4)
    .map((incident) => ({
      id: incident.id,

      kind: "incident",

      title: `${incident.severity}: ` + incident.title,

      description: incident.summary,

      occurredAt: incident.updatedAt,
    }));
}

/*
 * =========================================================
 * SAFE ERROR PRESENTATION
 * =========================================================
 */

function getOverviewErrorMessage(error: unknown): string {
  if (error instanceof OverviewRequestError) {
    if (error.status === 401) {
      return (
        "Your authenticated session is no longer available. " +
        "Please sign in again."
      );
    }

    if (error.status === 403) {
      return (
        "You do not have permission to view operational " + "Overview data."
      );
    }

    if (error.status === 502 || error.status === 503 || error.status === 504) {
      return (
        "The OpsFlow Overview service is temporarily unavailable. " +
        "Try loading the Overview again."
      );
    }
  }

  return (
    "OpsFlow could not load the current operational Overview. " + "Try again."
  );
}

/*
 * =========================================================
 * OVERVIEW PAGE
 * =========================================================
 */

export default function OverviewPage() {
  const [overviewState, setOverviewState] = useState<
    AsyncState<OverviewResponse>
  >(INITIAL_OVERVIEW_STATE);

  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => {
    let requestIsActive = true;

    getOverview()
      .then((overview) => {
        if (!requestIsActive) {
          return;
        }

        setOverviewState({
          status: "success",

          data: overview,

          error: null,
        });
      })
      .catch((error: unknown) => {
        if (!requestIsActive) {
          return;
        }

        setOverviewState({
          status: "error",

          data: null,

          error: getOverviewErrorMessage(error),
        });
      });

    return () => {
      requestIsActive = false;
    };
  }, [requestVersion]);

  function retryOverviewRequest(): void {
    setOverviewState(INITIAL_OVERVIEW_STATE);

    setRequestVersion((currentVersion) => currentVersion + 1);
  }

  const metrics =
    overviewState.status === "success"
      ? buildDashboardMetrics(
          overviewState.data.summary,
          overviewState.data.incidentDataAvailable,
        )
      : [];

  const activities =
    overviewState.status === "success" &&
    overviewState.data.incidentDataAvailable
      ? buildRecentActivity(overviewState.data.incidents)
      : [];

  return (
    <section aria-labelledby="overview-heading">
      <div className="dashboard-hero p-4 p-lg-5 mb-4">
        <p className="text-uppercase fw-semibold small mb-2">
          Operations command center
        </p>

        <h1 id="overview-heading" className="display-6 fw-bold mb-3">
          Fulfillment visibility without the noise.
        </h1>

        <p className="lead mb-0">
          Monitor operational health, fulfillment performance, and service
          reliability from one workspace.
        </p>
      </div>

      {overviewState.status === "loading" ? (
        <div
          className="card border-0 shadow-sm"
          aria-live="polite"
          aria-busy="true"
        >
          <div className="card-body p-5 text-center">
            <div className="spinner-border text-primary mb-3" role="status">
              <span className="visually-hidden">
                Loading operational Overview
              </span>
            </div>

            <p className="text-secondary mb-0">
              Loading current operational data…
            </p>
          </div>
        </div>
      ) : null}

      {overviewState.status === "error" ? (
        <div className="alert alert-danger" role="alert">
          <h2 className="h5">Overview unavailable</h2>

          <p>{overviewState.error}</p>

          <button
            type="button"
            className="btn btn-outline-danger"
            onClick={retryOverviewRequest}
          >
            Try again
          </button>
        </div>
      ) : null}

      {overviewState.status === "success" ? (
        <>
          {!overviewState.data.incidentDataAvailable ? (
            <div className="alert alert-warning" role="status">
              <h2 className="h5">Incident data temporarily unavailable</h2>

              <p>
                Service Catalog data is current, but OpsFlow could not retrieve
                Incident Management data. Incident metrics and recent activity
                are marked unavailable rather than being reported as zero.
              </p>

              <button
                type="button"
                className="btn btn-outline-dark"
                onClick={retryOverviewRequest}
              >
                Retry incident data
              </button>
            </div>
          ) : null}
          <section className="mb-4" aria-label="Key performance indicators">
            <div className="row g-4">
              {metrics.map((metric) => (
                <div className="col-12 col-sm-6 col-xl-3" key={metric.id}>
                  <MetricCard
                    label={metric.label}
                    value={metric.value}
                    supportingText={metric.supportingText}
                    accent={metric.accent}
                  />
                </div>
              ))}
            </div>
          </section>

          <div className="row g-4">
            <div className="col-12 col-xl-8">
              <RecentActivity
                activities={activities}
                incidentDataAvailable={overviewState.data.incidentDataAvailable}
              />
            </div>

            <div className="col-12 col-xl-4">
              <ServiceHealthSummary services={overviewState.data.services} />
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}
