export type DashboardView = "overview" | "services";

export type ServiceStatus = "Healthy" | "Degraded" | "Critical";

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
