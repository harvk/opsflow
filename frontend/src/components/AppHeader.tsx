import { NavLink, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/useAuth";

interface AppHeaderProps {
  isNavigationOpen: boolean;
  onToggleNavigation: () => void;
}

export default function AppHeader({
  isNavigationOpen,
  onToggleNavigation,
}: AppHeaderProps) {
  const navigate = useNavigate();

  const { user, logout } = useAuth();

  function handleSignOut() {
    logout();

    navigate("/login", {
      replace: true,
    });
  }

  return (
    <header className="ops-header">
      <div className="ops-header__inner">
        {/* Brand */}

        <div className="ops-header__brand">
          <div className="ops-header__brand-mark" aria-hidden="true">
            O
          </div>

          <div className="ops-header__brand-copy">
            <strong>OpsFlow</strong>

            <span>Operations Platform</span>
          </div>
        </div>

        {/* Desktop navigation */}

        <nav className="ops-header__nav" aria-label="Primary navigation">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `ops-nav-link ${isActive ? "ops-nav-link--active" : ""}`
            }
          >
            Overview
          </NavLink>

          <NavLink
            to="/services"
            className={({ isActive }) =>
              `ops-nav-link ${isActive ? "ops-nav-link--active" : ""}`
            }
          >
            Services
          </NavLink>

          <NavLink
            to="/incidents/new"
            className={({ isActive }) =>
              `ops-nav-link ${isActive ? "ops-nav-link--active" : ""}`
            }
          >
            Report incident
          </NavLink>
        </nav>

        {/* User controls */}

        <div className="ops-header__actions">
          <div className="ops-user-summary">
            <span className="ops-user-summary__name">
              {user?.full_name ?? user?.email ?? "Authenticated user"}
            </span>

            <span className="ops-user-summary__role">
              {user?.role ?? "OpsFlow user"}
            </span>
          </div>

          <button
            type="button"
            className="ops-signout-button"
            onClick={handleSignOut}
          >
            Sign out
          </button>

          <button
            type="button"
            className="ops-menu-button"
            onClick={onToggleNavigation}
            aria-expanded={isNavigationOpen}
            aria-controls="
              mobile-navigation
            "
            aria-label={
              isNavigationOpen ? "Close navigation" : "Open navigation"
            }
          >
            <span />
            <span />
            <span />
          </button>
        </div>
      </div>
    </header>
  );
}
