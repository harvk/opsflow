import { useEffect, useRef, useState } from "react";

import { Outlet, useLocation } from "react-router";

import AppHeader from "../components/AppHeader";
import AppSidebar from "../components/AppSidebar";

export default function AppLayout() {
  const location = useLocation();

  const mainRef = useRef<HTMLElement>(null);

  const [isNavigationOpen, setIsNavigationOpen] = useState(false);

  useEffect(() => {
    setIsNavigationOpen(false);

    mainRef.current?.focus();
  }, [location.pathname]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsNavigationOpen(false);
      }
    }

    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  function toggleNavigation() {
    setIsNavigationOpen((currentValue) => !currentValue);
  }

  return (
    <>
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>

      <div className="ops-app-shell">
        <AppSidebar
          isOpen={isNavigationOpen}
          onClose={() => setIsNavigationOpen(false)}
        />

        <div className="ops-app-shell__content">
          <AppHeader
            isNavigationOpen={isNavigationOpen}
            onToggleNavigation={toggleNavigation}
          />

          <main
            id="main-content"
            ref={mainRef}
            tabIndex={-1}
            className="ops-main-content"
          >
            <div className="container-fluid py-4 py-xl-5">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </>
  );
}
