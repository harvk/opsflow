import { Route, Routes } from "react-router-dom";

import { ProtectedRoute } from "./auth/ProtectedRoute";

import AppLayout from "./layouts/AppLayout";

import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";

import { LoginPage } from "./pages/LoginPage";

import { ResetPasswordPage } from "./pages/ResetPasswordPage";

import NotFoundPage from "./pages/NotFoundPage";

import OverviewPage from "./pages/OverviewPage";

import ServicesPage from "./pages/ServicesPage";

import ServiceDetailsPage from "./pages/ServiceDetailsPage";

import ReportIncidentPage from "./pages/ReportIncidentPage";

export default function App() {
  return (
    <Routes>
      {/*
       * ===================================================
       * PUBLIC AUTHENTICATION ROUTES
       * ===================================================
       */}

      <Route path="/login" element={<LoginPage />} />

      <Route path="/forgot-password" element={<ForgotPasswordPage />} />

      <Route path="/reset-password" element={<ResetPasswordPage />} />

      {/*
       * ===================================================
       * AUTHENTICATED APPLICATION
       * ===================================================
       */}

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<OverviewPage />} />

          <Route path="services" element={<ServicesPage />} />

          <Route path="services/:serviceId" element={<ServiceDetailsPage />} />

          <Route path="incidents/new" element={<ReportIncidentPage />} />

          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  );
}
