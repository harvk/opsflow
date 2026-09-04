export const SERVICE_STATUSES = ["Healthy", "Degraded", "Critical"] as const;

export type ServiceStatus = (typeof SERVICE_STATUSES)[number];

export const SERVICE_FILTER_STATUSES = ["All", ...SERVICE_STATUSES] as const;

export type ServiceFilterStatus = (typeof SERVICE_FILTER_STATUSES)[number];

export type AccentTone = "primary" | "success" | "warning" | "danger";

export interface Metric {
  id: string;
  label: string;
  value: string;
  supportingText: string;
  accent: AccentTone;
}

export interface Service {
  id: string;
  name: string;
  owner: string;
  status: ServiceStatus;
  uptime: string;
  latencyMs: number;
}

export interface ServiceDetails extends Service {
  description: string;
  region: string;
  version: string;
  lastDeployedAt: string;
  dependencies: string[];
}

export type AsyncState<T> =
  | {
      status: "loading";
      data: null;
      error: null;
    }
  | {
      status: "success";
      data: T;
      error: null;
    }
  | {
      status: "error";
      data: null;
      error: string;
    };

export function isServiceFilterStatus(
  value: string | null,
): value is ServiceFilterStatus {
  if (value === null) {
    return false;
  }

  return (SERVICE_FILTER_STATUSES as readonly string[]).includes(value);
}
