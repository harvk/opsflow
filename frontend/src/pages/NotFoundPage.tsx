import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <section className="ops-state-card text-center py-5">
      <p className="display-3 fw-bold mb-2">404</p>

      <h1 className="h3">Page not found</h1>

      <p className="text-secondary mb-4">
        The page you're looking for doesn't exist or may have moved.
      </p>

      <Link to="/" className="btn btn-primary">
        Return to dashboard
      </Link>
    </section>
  );
}
