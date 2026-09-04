import { useEffect, useState } from "react";

import EmptyState from "../components/ui/EmptyState";
import ErrorState from "../components/ui/ErrorState";
import LoadingState from "../components/ui/LoadingState";

import PageHeader from "../components/PageHeader";
import ServiceFilters from "../components/ServiceFilters";
import ServiceTable from "../components/ServiceTable";

import { getServices } from "../services/serviceClient";

import type {
  AsyncState,
  Service,
  ServiceFilterStatus,
} from "../types/dashboard";

const initialRequestState: AsyncState<Service[]> = {
  status: "loading",
  data: null,
  error: null,
};

export default function ServicesPage() {
  const [requestState, setRequestState] =
    useState<AsyncState<Service[]>>(initialRequestState);

  const [searchTerm, setSearchTerm] = useState("");

  const [statusFilter, setStatusFilter] = useState<ServiceFilterStatus>("All");

  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let ignore = false;

    async function loadServices() {
      setRequestState({
        status: "loading",
        data: null,
        error: null,
      });

      try {
        const serviceData = await getServices();

        if (!ignore) {
          setRequestState({
            status: "success",
            data: serviceData,
            error: null,
          });
        }
      } catch (error) {
        if (!ignore) {
          const message =
            error instanceof Error
              ? error.message
              : "An unexpected error occurred.";

          setRequestState({
            status: "error",
            data: null,
            error: message,
          });
        }
      }
    }

    void loadServices();

    return () => {
      ignore = true;
    };
  }, [reloadKey]);

  function handleResetFilters() {
    setSearchTerm("");
    setStatusFilter("All");
  }

  function handleRetry() {
    setReloadKey((currentValue) => currentValue + 1);
  }

  if (requestState.status === "loading") {
    return (
      <>
        <PageHeader
          eyebrow="Platform health"
          title="Services"
          description="Review the current health and performance of OpsFlow services."
        />

        <LoadingState message="Loading services..." />
      </>
    );
  }

  if (requestState.status === "error") {
    return (
      <>
        <PageHeader
          eyebrow="Platform health"
          title="Services"
          description="Review the current health and performance of OpsFlow services."
        />

        <ErrorState message={requestState.error} onRetry={handleRetry} />
      </>
    );
  }

  const normalizedSearch = searchTerm.trim().toLowerCase();

  const filteredServices = requestState.data.filter((service) => {
    const matchesSearch =
      service.name.toLowerCase().includes(normalizedSearch) ||
      service.owner.toLowerCase().includes(normalizedSearch);

    const matchesStatus =
      statusFilter === "All" || service.status === statusFilter;

    return matchesSearch && matchesStatus;
  });

  return (
    <section aria-labelledby="services-heading">
      <PageHeader
        eyebrow="Platform health"
        title="Services"
        description="Review, search, and filter the current health and performance of OpsFlow services."
      />

      <ServiceFilters
        searchTerm={searchTerm}
        status={statusFilter}
        resultCount={filteredServices.length}
        onSearchTermChange={setSearchTerm}
        onStatusChange={setStatusFilter}
        onReset={handleResetFilters}
      />

      {filteredServices.length === 0 ? (
        <EmptyState
          title="No services found"
          description="No services match the current search and status filters."
          actionLabel="Clear filters"
          onAction={handleResetFilters}
        />
      ) : (
        <ServiceTable services={filteredServices} />
      )}
    </section>
  );
}
