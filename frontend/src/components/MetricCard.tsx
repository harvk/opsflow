import type { AccentTone } from "../types/dashboard";

interface MetricCardProps {
  label: string;
  value: string;
  supportingText: string;
  accent?: AccentTone;
}

export default function MetricCard({
  label,
  value,
  supportingText,
  accent = "primary",
}: MetricCardProps) {
  return (
    <article
      className={`card h-100 border-0 shadow-sm ops-stat-card ops-stat-card--${accent}`}
    >
      <div className="card-body p-4">
        <h2 className="h6 text-secondary mb-2">{label}</h2>

        <p className="display-6 fw-semibold mb-2">{value}</p>

        <p className="small text-secondary mb-0">{supportingText}</p>
      </div>
    </article>
  );
}
