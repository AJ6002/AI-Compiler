# ADR-003: Durable Orchestration & State — Temporal and PostgreSQL

## Status
Accepted

## Context
Ingesting large or complex industrial spreadsheets involves multi-stage, potentially long-running pipelines (admission, discovery, execution, human review, publication) that must survive process crashes, worker restarts, and network partitions without losing state or generating duplicate published records.

## Decision
1. **PostgreSQL 16:** Relational store for contracts, recipe catalogues, tenant scope, and job metadata.
2. **Temporal Python SDK:** Durable workflow execution. Each parsing stage is isolated into deterministic activities with explicit timeouts, heartbeats, and retry policies.
3. **Local Docker Compose:** Containerized PostgreSQL and Temporal server provided for local development.

## Consequences
- Guaranteed state recovery without building custom retry loops or polling queues.
- Local development behavior mirrors production AWS / Temporal Cloud architecture.
