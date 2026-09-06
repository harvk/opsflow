import { NavLink } from "react-router-dom";

interface AppSidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function AppSidebar({ isOpen, onClose }: AppSidebarProps) {
  return (
    <>
      <div
        className={`ops-nav-overlay ${isOpen ? "ops-nav-overlay--open" : ""}`}
        onClick={onClose}
        aria-hidden="true"
      />

      <aside
        id="mobile-navigation"
        className={`ops-mobile-nav ${isOpen ? "ops-mobile-nav--open" : ""}`}
        aria-label="Mobile navigation"
      >
        <div className="ops-mobile-nav__header">
          <div>
            <strong>OpsFlow</strong>

            <span>Operations Platform</span>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="ops-mobile-nav__close"
            aria-label="Close navigation"
          >
            ×
          </button>
        </div>

        <nav className="ops-mobile-nav__links">
          <NavLink
            to="/"
            end
            onClick={onClose}
            className={({ isActive }) =>
              `ops-mobile-nav__link ${
                isActive ? "ops-mobile-nav__link--active" : ""
              }`
            }
          >
            Overview
          </NavLink>

          <NavLink
            to="/services"
            onClick={onClose}
            className={({ isActive }) =>
              `ops-mobile-nav__link ${
                isActive ? "ops-mobile-nav__link--active" : ""
              }`
            }
          >
            Services
          </NavLink>

          <NavLink
            to="/incidents/new"
            onClick={onClose}
            className={({ isActive }) =>
              `ops-mobile-nav__link ${
                isActive ? "ops-mobile-nav__link--active" : ""
              }`
            }
          >
            Report incident
          </NavLink>
        </nav>

        <footer className="ops-mobile-nav__footer">OpsFlow Frontend v1</footer>
      </aside>
    </>
  );
}
