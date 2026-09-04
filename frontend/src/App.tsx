import { Route, Routes } from "react-router";

import AppLayout from "./layouts/AppLayout";

import NotFoundPage from "./pages/NotFoundPage";
import OverviewPage from "./pages/OverviewPage";
import ServicesPage from "./pages/ServicesPage";

import ServiceDetailsPage from "./pages/ServiceDetailsPage";
import ReportIncidentPage from "./pages/ReportIncidentPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<OverviewPage />} />

        <Route path="services" element={<ServicesPage />} />

        <Route path="services/:serviceId" element={<ServiceDetailsPage />} />

        <Route path="incidents/new" element={<ReportIncidentPage />} />

        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
