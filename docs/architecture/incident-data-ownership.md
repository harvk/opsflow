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
    +-- ServiceRepository
```
