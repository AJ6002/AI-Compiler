# ADR-016: Hardened Docker Sandbox and Host-Side Supervisor

**Status:** ACCEPTED — IMPLEMENTED  
**Date:** 2026-10-25  
**Author:** AICONNEX Engineering Team  
**Governing Rule:** `AGENTS.md` (Untrusted Data Boundary, Immutability, Full Provenance, Zero Speculative Execution)

---

## 1. Context and Problem Statement

When deterministic layout discovery encounters ambiguous spreadsheet topology, an agent investigation layer must inspect the raw spreadsheet to formulate a declarative `ParsePlan`. Because uploaded workbooks and user-provided code can be adversarial, arbitrary code execution directly on the host or in an unconstrained container poses catastrophic security risks (remote code execution, host file tampering, data exfiltration, resource exhaustion).

Furthermore, the integration must enforce strict trust boundaries:
- The supervisor must never execute code proposed by an agent.
- The supervisor must never trust the agent's claim that a plan is safe.
- The supervisor must reject malformed outputs and enforce hard cgroup/security policies.

---

## 2. Decision: Hardened Docker Sandbox via Docker Python SDK

We decided to build the sandbox supervisor directly against `docker-py` (`docker>=7.1.0`) rather than high-level orchestrators such as `deepagents-docker` for Phase 3.

### 2.1 Why Defer `deepagents-docker`?
`deepagents-docker` provisions a single `shared_dir` mounted at `/shared`. In contrast, our industrial security spec requires strict capability segregation across three mounts:
1. `/input`: Host-provided read-only bind mount containing the original workbook bytes and `brief.json`.
2. `/work`: In-memory `tmpfs` (256MB) for ephemeral agent scratch files.
3. `/output`: Size-capped host directory accepting only the final `result.json` artifact.

`deepagents-docker` does not support this mount layout out of the box. Building on `docker-py` provides granular, native control over all container flags.

### 2.2 Container Security Flags (Single Source of Truth)

All containers spawned by `SandboxSupervisor` are configured via `HardenedContainerConfig`:

| Flag | Value | Security Mitigation |
|---|---|---|
| `network_mode` | `"none"` | Prevents data exfiltration, package downloads, and command-and-control calls. |
| `user` | `"1000:1000"` | Runs as unprivileged `sandbox` user, preventing host root escalation. |
| `read_only` | `True` | Makes container root filesystem immutable; prevents payload persistence. |
| `cap_drop` | `["ALL"]` | Drops all Linux capabilities (raw sockets, kernel module manipulation). |
| `security_opt` | `["no-new-privileges:true"]` | Disables `setuid` binaries and privilege escalation. |
| `pids_limit` | `64` | Defends against fork bombs and process table exhaustion. |
| `mem_limit` / `memswap_limit` | `"512m"` | Prevents host OOM attacks and disk swap thrashing. |
| `nano_cpus` | `1_000_000_000` | Limits execution to 1 CPU core to prevent noisy-neighbor starvation. |
| `tmpfs` | `{"/tmp": "size=64m", "/work": "size=256m"}` | Ephemeral, non-persistent scratch space in RAM. |

---

## 3. Host-Side Supervisor Lifecycle

The `SandboxSupervisor`:
1. Stages inputs into temporary host directories.
2. Spawns the hardened container with strict timeouts (90s default).
3. If timeout expires, issues `SIGTERM` followed by `SIGKILL` (exit code 137), cleans up container, and returns `SANDBOX_FAILED(reason="TIMEOUT")`.
4. Reads `/output/result.json` and parses it into `InvestigationResult` (Phase 1 contract).
5. If `status == "REVIEW_REQUIRED"`, routes directly to data stewards without executing.
6. If `status == "PLAN_PROPOSED"`, unwraps the `ParsePlan` and passes it through the Three-Level `PlanValidator` (Phase 2).
7. Guaranteed container removal and host temporary directory wiping in a `finally` block.

---

## 4. Consequences and Compliance

- **Untrusted Data Boundary:** All container execution occurs with zero host access and zero network access.
- **Model Decoupling:** Phase 3 requires no LLM dependencies. Verification is conducted with deterministic fake scripts.
- **Deterministic Pipeline Protection:** Workflow activities (`activities.py`) remain untouched until Phase 5.
