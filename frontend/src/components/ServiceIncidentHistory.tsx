import type { Incident } from "../types/incidents";

import { getIncidentSeverityPresentation } from "../utils/incidentPresentation";

interface ServiceIncidentHistoryProps {
  incidents: Incident[];
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function ServiceIncidentHistory({
  incidents,
}: ServiceIncidentHistoryProps) {
  const orderedIncidents = [...incidents].sort(
    (left, right) => Date.parse(right.createdAt) - Date.parse(left.createdAt),
  );

  return (
    <section
      className="card border-0 shadow-sm ops-service-incidents"
      aria-labelledby="service-incidents-heading"
    >
      <div className="card-body p-4 p-lg-5">
        <div className="d-flex flex-wrap align-items-start justify-content-between gap-3 mb-4">
          <div>
            <p className="ops-panel-eyebrow mb-2">Incident history</p>
            <h2 id="service-incidents-heading" className="h4 mb-1">
              Reported incidents
            </h2>
            <p className="small text-secondary mb-0">
              Every incident currently associated with this service.
            </p>
          </div>

          <span className="ops-incident-count-badge">
            {orderedIncidents.length} reported
          </span>
        </div>

        {orderedIncidents.length === 0 ? (
          <div className="ops-service-incidents-empty" role="status">
            No incidents have been reported for this service.
          </div>
        ) : (
          <ol className="ops-service-incident-list">
            {orderedIncidents.map((incident) => {
              const severity = getIncidentSeverityPresentation(
                incident.severity,
              );

              return (
                <li
                  key={incident.id}
                  className={`ops-service-incident ${severity.toneClass}`}
                >
                  <div className="ops-service-incident__heading">
                    <div className="ops-service-incident__title-group">
                      <span className="ops-service-incident__severity">
                        {severity.label}
                      </span>

                      <h3 className="ops-service-incident__title">
                        {incident.title}
                      </h3>
                    </div>

                    <span
                      className={[
                        "ops-service-incident__status",
                        incident.status === "Resolved"
                          ? "ops-service-incident__status--resolved"
                          : "",
                      ]
                        .filter(Boolean)
                        .join(" ")}
                    >
                      {incident.status}
                    </span>
                  </div>

                  <p className="ops-service-incident__summary">
                    {incident.summary}
                  </p>

                  <div className="ops-service-incident__meta">
                    <span>
                      <span className="ops-service-incident__meta-label">
                        Reported by
                      </span>
                      <strong>
                        {incident.reportedByEmail ?? "Legacy / system record"}
                      </strong>
                    </span>

                    <span>
                      <span className="ops-service-incident__meta-label">
                        Reported
                      </span>
                      <time dateTime={incident.createdAt}>
                        {formatDateTime(incident.createdAt)}
                      </time>
                    </span>

                    <span>
                      <span className="ops-service-incident__meta-label">
                        Assignee
                      </span>
                      <span>{incident.assignee}</span>
                    </span>
                  </div>

                  {incident.customerImpacting ? (
                    <span className="ops-impact-badge">Customer impacting</span>
                  ) : null}
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </section>
  );
}
