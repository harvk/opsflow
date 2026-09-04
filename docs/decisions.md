# Architecture Decisions

## ADR-001: Use React with TypeScript

Status: Accepted

React will provide the component-based SPA architecture while TypeScript
provides static type checking and improved maintainability.

---

## ADR-002: Use Python and FastAPI

Status: Accepted

Python will be used for backend services. FastAPI provides a modern,
type-driven framework suited for REST APIs and distributed services.

---

## ADR-003: Use Bootstrap with Custom CSS

Status: Accepted

Bootstrap will provide responsive layout primitives and reusable utilities.
Custom CSS will provide application-specific styling and demonstrate
fundamental CSS knowledge.

---

## ADR-004: Start Modular Before Extracting Microservices

Status: Accepted

The backend will initially favor clear modular boundaries before services
are separated into independently deployable microservices.

This allows service boundaries to emerge from actual application
requirements rather than premature distribution.
