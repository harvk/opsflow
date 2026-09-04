import { Link } from "react-router";

import type { Service, ServiceStatus } from "../types/dashboard";

interface ServiceHealthSummaryProps {
  services: Service[];
}

const STATUS_ORDER: ServiceStatus[] = ["Healthy", "Degraded", "Critical"];

export default function ServiceHealthSummary({
  services,
}: ServiceHealthSummaryProps) {
  const counts = STATUS_ORDER.map((status) => ({
    status,
    count: services.filter((service) => service.status === status).length,
  }));

  return (
    <section
      className="card border-0 shadow-sm h-100"
      aria-labelledby="health-summary-heading"
    >
      <div className="card-body p-4">
        <h2 id="health-summary-heading" className="h5">
          Service health
        </h2>

        <p className="small text-secondary">Current status distribution.</p>

        <div className="d-grid gap-3 mt-4">
          {counts.map(({ status, count }) => (
            <div
              key={status}
              className="d-flex align-items-center justify-content-between"
            >
              <span>{status}</span>

              <span className="fw-bold">{count}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="card-footer bg-white border-top p-4">
        <Link to="/services" className="btn btn-outline-primary w-100">
          View services
        </Link>
      </div>
    </section>
  );
}
