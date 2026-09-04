import type { FormEvent } from "react";

import type { ServiceFilterStatus } from "../types/dashboard";

interface ServiceFiltersProps {
  searchTerm: string;
  status: ServiceFilterStatus;
  resultCount: number;

  onSearchTermChange: (value: string) => void;

  onStatusChange: (status: ServiceFilterStatus) => void;

  onReset: () => void;
}

export default function ServiceFilters({
  searchTerm,
  status,
  resultCount,
  onSearchTermChange,
  onStatusChange,
  onReset,
}: ServiceFiltersProps) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
  }

  return (
    <form
      className="card border-0 shadow-sm mb-4"
      role="search"
      aria-label="Filter services"
      onSubmit={handleSubmit}
    >
      <div className="card-body">
        <div className="row g-3 align-items-end">
          <div className="col-12 col-lg-6">
            <label htmlFor="service-search" className="form-label fw-semibold">
              Search services
            </label>

            <input
              id="service-search"
              name="serviceSearch"
              type="search"
              className="form-control"
              placeholder="Search by service or owner"
              value={searchTerm}
              onChange={(event) => onSearchTermChange(event.target.value)}
            />
          </div>

          <div className="col-12 col-md-6 col-lg-3">
            <label htmlFor="service-status" className="form-label fw-semibold">
              Status
            </label>

            <select
              id="service-status"
              name="serviceStatus"
              className="form-select"
              value={status}
              onChange={(event) =>
                onStatusChange(event.target.value as ServiceFilterStatus)
              }
            >
              <option value="All">All statuses</option>

              <option value="Healthy">Healthy</option>

              <option value="Degraded">Degraded</option>

              <option value="Critical">Critical</option>
            </select>
          </div>

          <div className="col-12 col-md-6 col-lg-3">
            <button
              type="button"
              className="btn btn-outline-secondary w-100"
              onClick={onReset}
            >
              Clear filters
            </button>
          </div>
        </div>

        <p className="small text-secondary mt-3 mb-0" aria-live="polite">
          {resultCount === 1
            ? "1 service matches the current filters."
            : `${resultCount} services match the current filters.`}
        </p>
      </div>
    </form>
  );
}
