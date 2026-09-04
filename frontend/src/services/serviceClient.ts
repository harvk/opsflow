import { env } from "../config/env";
import { services } from "../data/dashboardData";

import type { Service, ServiceDetails } from "../types/dashboard";

import type { Incident, IncidentDraft } from "../types/incidents";

const MOCK_NETWORK_DELAY_MS = 500;

const SHOULD_SIMULATE_ERROR = false;

function wait(milliseconds: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${env.apiBaseUrl}${path}`, {
    ...init,

    headers: {
      "Content-Type": "application/json",

      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}.`);
  }

  return response.json() as Promise<T>;
}

export async function getServices(): Promise<Service[]> {
  if (!env.useMockApi) {
    return requestJson<Service[]>("/services");
  }

  await wait(MOCK_NETWORK_DELAY_MS);

  if (SHOULD_SIMULATE_ERROR) {
    throw new Error("Unable to load services.");
  }

  return services.map((service) => ({
    ...service,
  }));
}

export async function getServiceById(
  serviceId: string,
): Promise<ServiceDetails | null> {
  if (!env.useMockApi) {
    try {
      return await requestJson<ServiceDetails>(`/services/${serviceId}`);
    } catch (error) {
      throw error;
    }
  }

  await wait(MOCK_NETWORK_DELAY_MS);

  const service = services.find((candidate) => candidate.id === serviceId);

  if (!service) {
    return null;
  }

  return {
    ...service,
    dependencies: [...service.dependencies],
  };
}

export async function createIncident(draft: IncidentDraft): Promise<Incident> {
  if (!env.useMockApi) {
    return requestJson<Incident>("/incidents", {
      method: "POST",
      body: JSON.stringify(draft),
    });
  }

  await wait(MOCK_NETWORK_DELAY_MS);

  return {
    ...draft,
    id: `inc-${Date.now()}`,
    status: "Open",
    createdAt: new Date().toISOString(),
  };
}
