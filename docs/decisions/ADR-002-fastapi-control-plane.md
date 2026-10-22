# ADR-002: Control Plane API Framework — FastAPI and Pydantic v2

## Status
Accepted

## Context
The compiler requires a lightweight, strongly typed control plane to manage job lifecycles, validate client contracts, report execution progress, and expose review interfaces.

## Decision
Adopt **FastAPI** with **Pydantic v2**:
1. Seamless serialization and validation of complex JSON schemas (`ParsePlan`, `ClientContract`, `HandoffManifest`).
2. Native async support and OpenAPI documentation out of the box.
3. Separation of control plane (job orchestration and identity) from heavy computational data planes (isolated reader workers).

## Consequences
- Contracts defined in Pydantic serve as the single source of truth for API, database persistence, and documentation.
