interface EmptyStateProps {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}

export default function EmptyState({
  title,
  description,
  actionLabel,
  onAction,
}: EmptyStateProps) {
  const showAction = actionLabel && onAction;

  return (
    <div className="ops-state-card text-center">
      <div className="ops-empty-icon mx-auto mb-3" aria-hidden="true">
        0
      </div>

      <h2 className="h5">{title}</h2>

      <p className="text-secondary mb-3">{description}</p>

      {showAction && (
        <button
          type="button"
          className="btn btn-outline-primary"
          onClick={onAction}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
