import { useEffect, useRef, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";

import AppHeader from "../components/AppHeader";
import AppSidebar from "../components/AppSidebar";

import "../styles/app-shell.css";

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
    <div className="ops-app-viewport">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>

      <div className="ops-app-shell">
        <AppHeader
          isNavigationOpen={isNavigationOpen}
          onToggleNavigation={toggleNavigation}
        />

        <AppSidebar
          isOpen={isNavigationOpen}
          onClose={() => setIsNavigationOpen(false)}
        />

        <main
          id="main-content"
          ref={mainRef}
          tabIndex={-1}
          className="ops-main-content"
        >
          <div className="ops-content-container">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
