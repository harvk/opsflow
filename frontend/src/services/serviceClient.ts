import { apiFetch } from "../api/apiClient";

import type { Service, ServiceDetails } from "../types/dashboard";

import type {
  Incident,
  IncidentApiSeverity,
  IncidentCreateRequest,
  IncidentDraft,
  IncidentFormSeverity,
} from "../types/incidents";

const INCIDENT_SEVERITY_MAP: Record<IncidentFormSeverity, IncidentApiSeverity> =
  {
    Low: "SEV-4",
    Medium: "SEV-3",
    High: "SEV-2",
    Critical: "SEV-1",
  };

async function requestJson<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);

  headers.set("Accept", "application/json");

  if (
    init.body !== undefined &&
    init.body !== null &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }

  const response = await apiFetch(path, {
    ...init,
    headers,
  });

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}.`);
  }

  const data = (await response.json()) as T;

  return data;
}

export async function getServices(): Promise<Service[]> {
  return requestJson<Service[]>("/services", {
    method: "GET",
  });
}

export async function getServiceById(
  serviceId: string,
): Promise<ServiceDetails | null> {
  const response = await apiFetch(
    `/services/${encodeURIComponent(serviceId)}`,
    {
      method: "GET",

      headers: {
        Accept: "application/json",
      },
    },
  );

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}.`);
  }

  const data = (await response.json()) as ServiceDetails;

  return data;
}

export async function getServiceIncidents(
  serviceId: string,
): Promise<Incident[]> {
  const incidents: Incident[] = [];
  const pageSize = 100;
  let offset = 0;

  while (true) {
    const page = await requestJson<Incident[]>(
      `/services/${encodeURIComponent(serviceId)}/incidents` +
        `?offset=${offset}&limit=${pageSize}`,
      {
        method: "GET",
      },
    );

    incidents.push(...page);

    if (page.length < pageSize) {
      break;
    }

    offset += pageSize;
  }

  return incidents;
}

function toIncidentCreateRequest(draft: IncidentDraft): IncidentCreateRequest {
  return {
    serviceId: draft.serviceId,

    title: draft.title,

    severity: INCIDENT_SEVERITY_MAP[draft.severity],

    summary: draft.summary,

    assignee: draft.assignee,
  };
}

export async function createIncident(draft: IncidentDraft): Promise<Incident> {
  const request = toIncidentCreateRequest(draft);

  return requestJson<Incident>("/incidents", {
    method: "POST",

    body: JSON.stringify(request),
  });
}
