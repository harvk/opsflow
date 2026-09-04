interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

export default function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="ops-state-card" role="alert">
      <div className="d-flex flex-column flex-md-row align-items-md-center justify-content-between gap-3">
        <div>
          <h2 className="h5 mb-1">Something went wrong</h2>

          <p className="text-secondary mb-0">{message}</p>
        </div>

        {onRetry && (
          <button
            type="button"
            className="btn btn-outline-primary"
            onClick={onRetry}
          >
            Try again
          </button>
        )}
      </div>
    </div>
  );
}
