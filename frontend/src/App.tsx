import { useState } from "react";

import AppHeader from "./components/AppHeader";
import MetricCard from "./components/MetricCard";
import ServiceTable from "./components/ServiceTable";

import { dashboardMetrics, services } from "./data/dashboardData";

import type { DashboardView } from "./types/dashboard";

export default function App() {
  const [activeView, setActiveView] = useState<DashboardView>("overview");

  return (
    <>
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>

      <AppHeader activeView={activeView} onViewChange={setActiveView} />

      <p className="visually-hidden" aria-live="polite">
        {activeView === "overview"
          ? "Overview view displayed"
          : "Services view displayed"}
      </p>

      <main id="main-content" className="container py-4 py-lg-5" tabIndex={-1}>
        {activeView === "overview" ? (
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
        ) : (
          <section aria-labelledby="services-heading">
            <div className="mb-4">
              <p className="text-uppercase text-secondary fw-semibold small mb-2">
                Platform health
              </p>

              <h1 id="services-heading" className="h2 mb-2">
                Services
              </h1>

              <p className="text-secondary mb-0">
                Review the current health and performance of OpsFlow services.
              </p>
            </div>

            <ServiceTable services={services} />
          </section>
        )}
      </main>
    </>
  );
}
