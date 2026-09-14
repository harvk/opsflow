# Incident Data Ownership

## Status

Accepted for staged implementation.

## Date

2026-09-12

## Context

OpsFlow currently runs Incident Management inside the Core
Backend process.

The Incident API has been moved behind the application-level
`IncidentGateway` contract. The current implementation is
`LocalIncidentGateway`, which delegates to the existing
in-process `IncidentService`.

The current request path is:

```text
FastAPI route
    |
    v
IncidentGateway
    |
    v
LocalIncidentGateway
    |
    v
IncidentService
    |
    +-- IncidentRepository
    |
    +-- ServiceCatalogGateway
```

Incident records currently reside in the Core Backend's
`opsflow` and `opsflow_test` databases.

The existing `incidents` table also has a database foreign key
to the Core Backend-owned `services` table.

That arrangement prevents Incident Management from owning its
persistence lifecycle independently.

## Decision

Incident Management will own separate logical PostgreSQL
databases on the existing OpsFlow PostgreSQL server.

The Incident Service databases are:

```text
opsflow_incidents
opsflow_incidents_test
```

The Core Backend continues to own:

```text
opsflow
opsflow_test
```

Using one PostgreSQL server is an infrastructure decision for
the current deployment. It does not make the databases jointly
owned.

The database boundary allows Incident Management to move to a
separate PostgreSQL server later without changing its
application ownership model.

## Incident-owned resources

The Incident Service owns:

- the `incidents` table in its databases;
- the `incident_severity` PostgreSQL enum;
- the `incident_status` PostgreSQL enum;
- all Incident indexes and constraints;
- its own `alembic_version` table;
- its own Alembic revisions;
- its own SQLAlchemy metadata;
- its own production and test database configuration.

The Incident Service must not register or migrate Core
Backend-owned models.

These include:

- `ServiceModel`;
- `UserModel`;
- `AuthSessionModel`;
- `ServiceDependencyModel`.

## Migration ownership

The Core Backend migration history applies only to:

```text
opsflow
opsflow_test
```

The Incident Service migration history applies only to:

```text
opsflow_incidents
opsflow_incidents_test
```

The Core Backend's current Alembic head is:

```text
954a9e3b2f31
```

Creating an independent Incident migration history must not
alter that revision or establish a dependency on it.

The first Incident Service revision is an independent Alembic
root revision. Its `down_revision` is `None`.

The Core Backend must never execute its Alembic history against
an Incident Service database.

The Incident Service must never execute its Alembic history
against a Core Backend database.

## Service references

`Incident.service_id` remains a required UUID.

It is an external Service Catalog reference rather than a
relational reference to a locally owned Service record.

The Incident database must not contain:

```text
FOREIGN KEY (service_id) REFERENCES services(id)
```

The Incident Service must not define:

```python
ServiceModel
relationship("ServiceModel")
```

Service existence is validated through the
`ServiceCatalogGateway`.

It is not validated through:

- a cross-database query;
- a cross-schema join;
- shared SQLAlchemy metadata;
- a database foreign key;
- direct access to the Core Backend's Service repository.

## Transaction boundary

Incident data and Service Catalog data no longer participate in
one database transaction.

Incident Management commits Incident changes in its own
database.

Service-reference validation is a service-level operation and
does not create a distributed database transaction.

Temporary cross-service inconsistency must be handled through
application behavior rather than a cross-database constraint.

## Database provisioning

Fresh PostgreSQL volumes create the required logical databases
through PostgreSQL initialization SQL.

PostgreSQL initialization scripts run only when the database
data directory is empty.

Existing OpsFlow PostgreSQL volumes therefore require an
idempotent one-shot database-provisioning operation.

That operation:

1. Checks whether each required database exists.
2. Creates only missing databases.
3. Leaves existing databases and data unchanged.
4. Runs before either migration service.
5. Can safely run again during future Compose startups.

Provisioning the new Incident databases does not authorize
resetting or deleting the existing PostgreSQL volume.

## Test ownership

Incident Service persistence tests use:

```text
opsflow_incidents_test
```

Core Backend tests continue using:

```text
opsflow_test
```

The two test suites must not share database state or migration
history.

## Staged data-migration strategy

Incident extraction uses a staged migration.

During the transition:

1. Existing Incident data remains in `opsflow.incidents`.
2. A new empty `opsflow_incidents.incidents` table is created.
3. The standalone Incident implementation is tested against
   its owned database.
4. A later phase copies existing Incident rows into the new
   database.
5. Row counts and field-level data are verified.
6. The Core Backend switches from `LocalIncidentGateway` to
   the HTTP gateway only after verification.
7. The old Core Backend Incident table remains available during
   rollback validation.
8. Removal of the old table requires a separate explicit
   cleanup decision.

This phase does not delete, rename, truncate, or modify the
existing Core Backend `incidents` table.

## Consequences

### Positive consequences

- Incident Management owns its schema and migration history.
- The service can evolve Incident persistence independently.
- No cross-service database foreign key remains.
- Core Backend and Incident tests use isolated databases.
- Migration failures are isolated by service.
- A future separate PostgreSQL server requires fewer
  application changes.
- The service boundary is visible in both code and deployment
  configuration.

### Operational costs

- Database provisioning becomes explicit.
- Two Alembic histories must be maintained.
- Cross-service joins are unavailable.
- Cross-service changes cannot use one database transaction.
- Service-reference validation requires a gateway operation.
- Data migration and traffic cutover require staged
  verification.
- Local development manages additional logical databases.

## Rejected alternatives

### Continue using Core Backend tables

Rejected because Incident Management would not own its
persistence lifecycle.

The service would remain coupled to Core Backend migrations,
metadata, and database availability.

### Use a separate schema in the `opsflow` database

Rejected because a shared database would retain a common
database-level lifecycle and make accidental cross-schema
coupling easier.

A separate schema would also make cross-service joins and
foreign keys technically convenient, undermining the intended
boundary.

### Introduce a second PostgreSQL container immediately

Rejected for the current stage because a separate logical
database on the existing PostgreSQL server provides the
required ownership boundary with less local operational
complexity.

This decision does not prevent moving the Incident databases to
a dedicated PostgreSQL server later.

### Delete or move the existing Incident table immediately

Rejected because it would combine:

- database provisioning;
- schema creation;
- data migration;
- traffic cutover;
- rollback removal;
- destructive cleanup.

Those operations must remain separate and independently
verifiable.
