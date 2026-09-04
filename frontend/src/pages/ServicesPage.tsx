import { useSearchParams } from "react-router";

import EmptyState from "../components/ui/EmptyState";
import ErrorState from "../components/ui/ErrorState";
import LoadingState from "../components/ui/LoadingState";

import PageHeader from "../components/PageHeader";
import ServiceFilters from "../components/ServiceFilters";
import ServiceTable from "../components/ServiceTable";

import { useServices } from "../hooks/useServices";

import { isServiceFilterStatus } from "../types/dashboard";

import type { ServiceFilterStatus } from "../types/dashboard";

export default function ServicesPage() {
  const { requestState, retry } = useServices();

  const [searchParams, setSearchParams] = useSearchParams();

  const searchTerm = searchParams.get("q") ?? "";

  const statusParameter = searchParams.get("status");

  const statusFilter: ServiceFilterStatus = isServiceFilterStatus(
    statusParameter,
  )
    ? statusParameter
    : "All";

  function handleSearchTermChange(value: string) {
    setSearchParams(
      (currentParams) => {
        const nextParams = new URLSearchParams(currentParams);

        if (value.trim()) {
          nextParams.set("q", value);
        } else {
          nextParams.delete("q");
        }

        return nextParams;
      },
      {
        replace: true,
      },
    );
  }

  function handleStatusChange(status: ServiceFilterStatus) {
    setSearchParams(
      (currentParams) => {
        const nextParams = new URLSearchParams(currentParams);

        if (status === "All") {
          nextParams.delete("status");
        } else {
          nextParams.set("status", status);
        }

        return nextParams;
      },
      {
        replace: true,
      },
    );
  }

  function handleResetFilters() {
    setSearchParams(
      {},
      {
        replace: true,
      },
    );
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

        <ErrorState message={requestState.error} onRetry={retry} />
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
    <section>
      <PageHeader
        eyebrow="Platform health"
        title="Services"
        description="Review, search, and filter the current health and performance of OpsFlow services."
      />

      <ServiceFilters
        searchTerm={searchTerm}
        status={statusFilter}
        resultCount={filteredServices.length}
        onSearchTermChange={handleSearchTermChange}
        onStatusChange={handleStatusChange}
        onReset={handleResetFilters}
      />

      {filteredServices.length === 0 ? (
        <EmptyState
          title="No services found"
          description="No services match the current filters."
          actionLabel="Clear filters"
          onAction={handleResetFilters}
        />
      ) : (
        <ServiceTable services={filteredServices} />
      )}
    </section>
  );
}
