import type { ActivityItem } from "../types/dashboard";

interface RecentActivityProps {
  activities: ActivityItem[];
}

function formatActivityTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function RecentActivity({ activities }: RecentActivityProps) {
  return (
    <section
      className="card border-0 shadow-sm h-100"
      aria-labelledby="recent-activity-heading"
    >
      <div className="card-body p-4">
        <div className="mb-4">
          <h2 id="recent-activity-heading" className="h5 mb-1">
            Recent activity
          </h2>

          <p className="small text-secondary mb-0">
            Latest operational events across OpsFlow.
          </p>
        </div>

        <ol className="ops-activity-list">
          {activities.map((activity) => (
            <li key={activity.id} className="ops-activity-item">
              <div>
                <p className="fw-semibold mb-1">{activity.title}</p>

                <p className="small text-secondary mb-2">
                  {activity.description}
                </p>

                <time
                  className="small text-secondary"
                  dateTime={activity.occurredAt}
                >
                  {formatActivityTime(activity.occurredAt)}
                </time>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
