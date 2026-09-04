interface LoadingStateProps {
  message?: string;
}

export default function LoadingState({
  message = "Loading data...",
}: LoadingStateProps) {
  return (
    <div
      className="ops-state-card text-center"
      role="status"
      aria-live="polite"
    >
      <div className="spinner-border text-primary mb-3" aria-hidden="true" />

      <p className="mb-0 text-secondary">{message}</p>
    </div>
  );
}
