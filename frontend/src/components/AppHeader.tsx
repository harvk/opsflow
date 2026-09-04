import { NavLink } from "react-router";

export default function AppHeader() {
  return (
    <header className="ops-header">
      <div className="container py-3">
        <div className="d-flex flex-column flex-lg-row align-items-lg-center justify-content-between gap-3">
          <NavLink to="/" className="ops-brand text-decoration-none">
            <span className="ops-brand-mark" aria-hidden="true">
              O
            </span>

            <span className="fw-bold fs-4">OpsFlow</span>
          </NavLink>

          <nav className="app-nav d-flex gap-2" aria-label="Primary navigation">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                isActive ? "btn btn-primary" : "btn btn-outline-secondary"
              }
            >
              Overview
            </NavLink>

            <NavLink
              to="/services"
              className={({ isActive }) =>
                isActive ? "btn btn-primary" : "btn btn-outline-secondary"
              }
            >
              Services
            </NavLink>
          </nav>
        </div>
      </div>
    </header>
  );
}
