import type { DashboardView } from "../types/dashboard";

interface AppHeaderProps {
  activeView: DashboardView;
  onViewChange: (view: DashboardView) => void;
}

export default function AppHeader({
  activeView,
  onViewChange,
}: AppHeaderProps) {
  return (
    <header className="ops-header">
      <div className="container py-3">
        <div className="d-flex flex-column flex-lg-row align-items-lg-center justify-content-between gap-3">
          <div className="d-flex align-items-center gap-2">
            <span className="ops-brand-mark" aria-hidden="true">
              O
            </span>

            <span className="fw-bold fs-4">OpsFlow</span>
          </div>

          <nav className="app-nav d-flex gap-2" aria-label="Primary navigation">
            <button
              type="button"
              className={
                activeView === "overview"
                  ? "btn btn-primary"
                  : "btn btn-outline-secondary"
              }
              aria-pressed={activeView === "overview"}
              onClick={() => onViewChange("overview")}
            >
              Overview
            </button>

            <button
              type="button"
              className={
                activeView === "services"
                  ? "btn btn-primary"
                  : "btn btn-outline-secondary"
              }
              aria-pressed={activeView === "services"}
              onClick={() => onViewChange("services")}
            >
              Services
            </button>
          </nav>
        </div>
      </div>
    </header>
  );
}
