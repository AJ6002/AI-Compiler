# Phase 1 Reference: Macro-Architectural Mapping

This reference guides the agent to map the overall architecture of the codebase before modifying any files.

---

## 1. System Topology Discovery

Before making assumptions about how an application works, locate and inspect structural root files:

1. **Project Definition Files:**
   - Look for files that declare frameworks, libraries, and runtime versions:
     - Python: `pyproject.toml`, `setup.py`, `requirements.txt`, `Pipfile`
     - Node / TypeScript: `package.json`, `tsconfig.json`
     - Go: `go.mod`
     - Rust: `Cargo.toml`
2. **Infrastructure and Orchestration:**
   - Review container and service declarations:
     - `docker-compose.yml`, `Dockerfile`, `k8s/`, Helm charts.
   - Determine which external services (PostgreSQL, Redis, Kafka, Elasticsearch) the code depends on.
3. **Application Entry Points:**
   - Identify entry point files where execution begins:
     - `main.py`, `app.py`, `server.ts`, `index.ts`, `manage.py`, `cmd/main.go`.
   - Identify top-level router and controller registrations.

---

## 2. Tracing End-to-End Data Flows

Do not look at individual functions in isolation. Follow data as it flows through the system:

1. **Ingress Layer:**
   - Where do requests enter the system (HTTP endpoints, message queues, scheduled jobs)?
   - What is the format and schema of incoming requests?
2. **Business Logic Layer:**
   - Which service or controller processes the validated request?
   - How are errors handled and logged?
3. **Egress and Persistence Layer:**
   - Which models, database tables, or external APIs are updated or queried?
   - Are transactions or idempotency keys required?

---

## 3. Context Compaction Continuity

When working across long sessions where previous conversations are summarized:

1. **Chain of Events:**
   - Treat work across summarized sessions as one continuous chain of events.
   - Do not restart discovery from scratch if previous decisions were summarized.
2. **Preserve Current State:**
   - Inspect the current repository status (`git status`) to know which files were already modified.
   - Reconnect current instructions to prior accepted requirements.
