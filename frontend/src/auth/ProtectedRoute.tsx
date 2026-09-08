import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "./useAuth";

export function ProtectedRoute() {
  const { isAuthenticated, isInitializing } = useAuth();

  const location = useLocation();

  if (isInitializing) {
    return (
      <div
        className="
          d-flex
          min-vh-100
          align-items-center
          justify-content-center
        "
        role="status"
        aria-live="polite"
      >
        <div className="text-center">
          <div
            className="
              spinner-border
              text-primary
              mb-3
            "
            aria-hidden="true"
          />

          <p className="text-secondary mb-0">Loading OpsFlow...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        replace
        state={{
          from: location,
        }}
      />
    );
  }

  return <Outlet />;
}
