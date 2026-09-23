import { useEffect, useState } from "react";

import type { ActivityItem } from "../types/dashboard";

import { getIncidentSeverityPresentation } from "../utils/incidentPresentation";

interface RecentActivityProps {
  activities: ActivityItem[];

  incidentDataAvailable: boolean;
}

const ACTIVITIES_PER_PAGE = 4;

function formatActivityTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function RecentActivity({
  activities,
  incidentDataAvailable,
}: RecentActivityProps) {
  const [page, setPage] = useState(1);

  const totalPages = Math.max(
    1,
    Math.ceil(activities.length / ACTIVITIES_PER_PAGE),
  );

  const currentPage = Math.min(page, totalPages);

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  const pageStart = (currentPage - 1) * ACTIVITIES_PER_PAGE;
  const visibleActivities = activities.slice(
    pageStart,
    pageStart + ACTIVITIES_PER_PAGE,
  );

  const isFirstPage = currentPage === 1;
  const isLastPage = currentPage === totalPages;

  const goToFirstPage = () => {
    setPage(1);
  };

  const goToPreviousPage = () => {
    setPage((value) => Math.max(1, value - 1));
  };

  const goToNextPage = () => {
    setPage((value) => Math.min(totalPages, value + 1));
  };

  const goToLastPage = () => {
    setPage(totalPages);
  };

  return (
    <section
      className="card border-0 shadow-sm h-100 ops-panel ops-activity-panel"
      aria-labelledby="recent-activity-heading"
    >
      <div className="card-body p-4 p-lg-5">
        <div className="ops-panel-heading mb-4">
          <div>
            <p className="ops-panel-eyebrow mb-2">Incident stream</p>
            <h2 id="recent-activity-heading" className="h4 mb-1">
              Recent activity
            </h2>
            <p className="small text-secondary mb-0">
              Latest incident reports and ownership across OpsFlow.
            </p>
          </div>

          <span className="ops-live-indicator">
            <span aria-hidden="true" />
            Live
          </span>
        </div>

        {!incidentDataAvailable ? (
          <p className="text-warning-emphasis mb-0" role="status">
            Recent incident activity is temporarily unavailable.
          </p>
        ) : activities.length === 0 ? (
          <p className="text-secondary mb-0" role="status">
            No recent incident activity is available.
          </p>
        ) : (
          <>
            <ol className="ops-activity-list">
              {visibleActivities.map((activity) => {
                const severity = getIncidentSeverityPresentation(
                  activity.severity,
                );
                const isResolved = activity.status === "Resolved";

                return (
                  <li
                    key={activity.id}
                    className={[
                      "ops-activity-item",
                      severity.toneClass,
                      isResolved ? "ops-activity-item--resolved" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                  >
                    <span className="ops-activity-marker" aria-hidden="true" />

                    <div className="ops-activity-content">
                      <div className="ops-activity-title-row">
                        <p className="ops-activity-title mb-0">
                          <span className="ops-activity-severity-label">
                            {severity.label}
                          </span>
                          <span aria-hidden="true">: </span>
                          <span>{activity.title}</span>
                        </p>

                        <span
                          className={[
                            "ops-activity-status",
                            isResolved
                              ? "ops-activity-status--resolved"
                              : "",
                          ]
                            .filter(Boolean)
                            .join(" ")}
                        >
                          {activity.status}
                        </span>
                      </div>

                      <p className="ops-activity-description">
                        {activity.description}
                      </p>

                      <div className="ops-activity-meta">
                        <span className="ops-activity-meta-item">
                          <span className="ops-activity-meta-label">
                            Reported by
                          </span>
                          <strong>
                            {activity.reportedByEmail ??
                              "Legacy / system record"}
                          </strong>
                        </span>

                        <span className="ops-activity-meta-item">
                          <span className="ops-activity-meta-label">
                            Reported
                          </span>
                          <time dateTime={activity.occurredAt}>
                            {formatActivityTime(activity.occurredAt)}
                          </time>
                        </span>

                        <span className="ops-activity-meta-item">
                          <span className="ops-activity-meta-label">
                            Assignee
                          </span>
                          <span>{activity.assignee}</span>
                        </span>
                      </div>

                      {activity.customerImpacting ? (
                        <span className="ops-impact-badge">
                          Customer impacting
                        </span>
                      ) : null}
                    </div>
                  </li>
                );
              })}
            </ol>

            <nav
              className="ops-activity-pagination"
              aria-label="Recent activity pagination"
            >
              <button
                type="button"
                className="ops-activity-page-button"
                onClick={goToFirstPage}
                disabled={isFirstPage}
                aria-label="Go to first page"
              >
                &lt;&lt;
              </button>

              <button
                type="button"
                className="ops-activity-page-button"
                onClick={goToPreviousPage}
                disabled={isFirstPage}
                aria-label="Go to previous page"
              >
                &lt;
              </button>

              <span
                className="ops-activity-page-status"
                aria-live="polite"
                aria-atomic="true"
              >
                {currentPage} of {totalPages}
              </span>

              <button
                type="button"
                className="ops-activity-page-button"
                onClick={goToNextPage}
                disabled={isLastPage}
                aria-label="Go to next page"
              >
                &gt;
              </button>

              <button
                type="button"
                className="ops-activity-page-button"
                onClick={goToLastPage}
                disabled={isLastPage}
                aria-label="Go to last page"
              >
                &gt;&gt;
              </button>
            </nav>
          </>
        )}
      </div>
    </section>
  );
}
