import MetricCard from "../components/MetricCard";
import { dashboardMetrics } from "../data/dashboardData";

export default function OverviewPage() {
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

      <div className="row g-4">
        {dashboardMetrics.map((metric) => (
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
  );
}
