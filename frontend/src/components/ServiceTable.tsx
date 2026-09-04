import type { Service } from "../types/dashboard";

import { Link } from "react-router";

import StatusBadge from "./StatusBadge";

interface ServiceTableProps {
  services: Service[];
}

export default function ServiceTable({ services }: ServiceTableProps) {
  return (
    <div className="card border-0 shadow-sm overflow-hidden">
      <div className="table-responsive">
        <table className="table table-hover align-middle mb-0">
          <caption className="visually-hidden">
            Current OpsFlow service health and performance
          </caption>

          <thead className="table-light">
            <tr>
              <th scope="col">Service</th>

              <th scope="col">Owner</th>

              <th scope="col">Status</th>

              <th scope="col">Uptime</th>

              <th scope="col">Latency</th>
            </tr>
          </thead>

          <tbody>
            {services.map((service) => (
              <tr key={service.id}>
                <th scope="row">
                  <Link
                    to={`/services/${service.id}`}
                    className="fw-semibold text-decoration-none"
                  >
                    {service.name}
                  </Link>
                </th>

                <td>{service.owner}</td>

                <td>
                  <StatusBadge status={service.status} />
                </td>

                <td>{service.uptime}</td>

                <td>{service.latencyMs} ms</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
