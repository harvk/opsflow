import { NavLink } from "react-router";

interface AppSidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function AppSidebar({ isOpen, onClose }: AppSidebarProps) {
  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    ["ops-sidebar-link", isActive ? "ops-sidebar-link--active" : ""]
      .filter(Boolean)
      .join(" ");

  return (
    <>
      <aside
        id="primary-navigation"
        className={["ops-sidebar", isOpen ? "ops-sidebar--open" : ""]
          .filter(Boolean)
          .join(" ")}
        aria-label="Application navigation"
      >
        <div className="ops-sidebar__header">
          <NavLink
            to="/"
            className="ops-brand text-decoration-none"
            onClick={onClose}
          >
            <span className="ops-brand-mark" aria-hidden="true">
              O
            </span>

            <span className="fw-bold fs-4">OpsFlow</span>
          </NavLink>

          <button
            type="button"
            className="btn-close d-lg-none"
            aria-label="Close navigation"
            onClick={onClose}
          />
        </div>

        <nav className="ops-sidebar__nav" aria-label="Primary navigation">
          <NavLink to="/" end className={navLinkClass} onClick={onClose}>
            <span>Overview</span>
          </NavLink>

          <NavLink to="/services" className={navLinkClass} onClick={onClose}>
            <span>Services</span>
          </NavLink>

          <NavLink
            to="/incidents/new"
            className={navLinkClass}
            onClick={onClose}
          >
            <span>Report incident</span>
          </NavLink>
        </nav>

        <div className="ops-sidebar__footer">
          <p className="small text-secondary mb-1">OpsFlow Platform</p>

          <p className="small text-secondary mb-0">Frontend v1</p>
        </div>
      </aside>

      {isOpen && (
        <button
          type="button"
          className="ops-sidebar-backdrop d-lg-none"
          aria-label="Close navigation"
          onClick={onClose}
        />
      )}
    </>
  );
}
