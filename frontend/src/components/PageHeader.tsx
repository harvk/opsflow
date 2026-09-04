interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
}

export default function PageHeader({
  eyebrow,
  title,
  description,
}: PageHeaderProps) {
  return (
    <header className="mb-4">
      {eyebrow && (
        <p className="text-uppercase text-secondary fw-semibold small mb-2">
          {eyebrow}
        </p>
      )}

      <h1 className="h2 mb-2">{title}</h1>

      {description && <p className="text-secondary mb-0">{description}</p>}
    </header>
  );
}
