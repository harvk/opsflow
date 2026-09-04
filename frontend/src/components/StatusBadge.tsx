import type { ServiceStatus } from "../types/dashboard";

interface StatusBadgeProps {
  status: ServiceStatus;
}

const statusClasses: Record<ServiceStatus, string> = {
  Healthy: "text-bg-success",
  Degraded: "text-bg-warning",
  Critical: "text-bg-danger",
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span className={`badge rounded-pill ${statusClasses[status]}`}>
      {status}
    </span>
  );
}
