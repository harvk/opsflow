import { Outlet, useLocation } from "react-router";
import { useEffect, useRef } from "react";

import AppHeader from "../components/AppHeader";

export default function AppLayout() {
  const location = useLocation();

  const mainRef = useRef<HTMLElement>(null);

  useEffect(() => {
    mainRef.current?.focus();
  }, [location.pathname]);

  return (
    <>
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>

      <AppHeader />

      <main
        id="main-content"
        ref={mainRef}
        tabIndex={-1}
        className="container py-4 py-lg-5"
      >
        <Outlet />
      </main>
    </>
  );
}
