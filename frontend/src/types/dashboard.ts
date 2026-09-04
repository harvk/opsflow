export type ServiceStatus = "Healthy" | "Degraded" | "Critical";

export type ServiceFilterStatus = "All" | ServiceStatus;

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
