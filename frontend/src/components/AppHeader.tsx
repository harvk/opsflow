interface AppHeaderProps {
  isNavigationOpen: boolean;
  onToggleNavigation: () => void;
}

export default function AppHeader({
  isNavigationOpen,
  onToggleNavigation,
}: AppHeaderProps) {
  return (
    <header className="ops-mobile-header d-lg-none">
      <div className="container-fluid d-flex align-items-center justify-content-between py-3">
        <div className="d-flex align-items-center gap-2">
          <span className="ops-brand-mark" aria-hidden="true">
            O
          </span>

          <span className="fw-bold fs-5">OpsFlow</span>
        </div>

        <button
          type="button"
          className="btn btn-outline-secondary"
          aria-controls="primary-navigation"
          aria-expanded={isNavigationOpen}
          aria-label="Toggle navigation"
          onClick={onToggleNavigation}
        >
          Menu
        </button>
      </div>
    </header>
  );
}
