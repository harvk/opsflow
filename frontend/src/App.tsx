import { Route, Routes } from "react-router-dom";

import AppLayout from "./layouts/AppLayout";

import { ProtectedRoute } from "./auth/ProtectedRoute";

import { LoginPage } from "./pages/LoginPage";
import NotFoundPage from "./pages/NotFoundPage";
import OverviewPage from "./pages/OverviewPage";
import ServicesPage from "./pages/ServicesPage";

import ServiceDetailsPage from "./pages/ServiceDetailsPage";
import ReportIncidentPage from "./pages/ReportIncidentPage";

export default function App() {
  return (
    <Routes>
      {/* Public route */}
      <Route path="/login" element={<LoginPage />} />

      {/* Authenticated application */}
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          {/* Dashboard / overview */}
          <Route index element={<OverviewPage />} />

          {/* Services */}
          <Route path="services" element={<ServicesPage />} />

          <Route path="services/:serviceId" element={<ServiceDetailsPage />} />

          {/* Incidents */}
          <Route path="incidents/new" element={<ReportIncidentPage />} />

          {/* Authenticated 404 */}
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  );
}
