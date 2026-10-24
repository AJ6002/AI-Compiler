# Sandbox Operations Runbook

**Service:** AICONNEX Investigation Container Sandbox  
**Component:** `SandboxSupervisor` (`src/compiler/investigation/supervisor.py`)  
**Base Image:** `aiconnex-sandbox:latest` (`docker/sandbox/Dockerfile`)

---

## 1. Rebuilding the Sandbox Image

Whenever dependencies in `pyproject.toml` are upgraded (e.g. `pyarrow`, `python-calamine`, `openpyxl`), the sandbox base image must be rebuilt to match the host compiler:

```bash
docker build -t aiconnex-sandbox:latest -f docker/sandbox/Dockerfile .
```

To verify the image build and non-root user ID:
```bash
docker run --rm aiconnex-sandbox:latest id -u
# Expected output: 1000
```

---

## 2. Enabling gVisor (`runsc`) for Production

In hardened production clusters, gVisor provides a userspace application kernel between the container and host Linux kernel.

1. Install `runsc` on the host machine:
   ```bash
   sudo apt-get install -y runsc
   sudo runsc install
   sudo systemctl restart docker
   ```
2. Verify Docker detects the runtime:
   ```bash
   docker info | grep -i runsc
   # Output should list: Runtimes: runsc runc ...
   ```
3. Initialize `SandboxSupervisor` with `runtime="runsc"`:
   ```python
   supervisor = SandboxSupervisor(
       image="aiconnex-sandbox:latest",
       runtime="runsc",
       timeout_s=90,
   )
   ```

---

## 3. Investigating a Failed Sandbox Execution

When a container run returns `SANDBOX_FAILED`:
1. Check `outcome.failure_reason`:
   - `TIMEOUT`: Container exceeded wall-clock limit (default 90s). Process was killed with `SIGKILL`.
   - `NO_OUTPUT`: Container completed or crashed without creating `/output/result.json`.
   - `CONTRACT_VIOLATION`: `result.json` was generated but failed Pydantic validation against `InvestigationResult`.
   - `DOCKER_UNAVAILABLE`: Docker daemon was stopped, unreachable, or permission denied on socket.
2. Inspect `outcome.metadata.logs`:
   Supervisor automatically attaches container `stdout`/`stderr` logs and Pydantic validation tracebacks into `metadata.logs`.

---

## 4. Container Cleanup and Orphan Management

All containers are created with label `aiconnex-sandbox=true`. If host crashes abruptly mid-turn, prune orphaned containers:

```bash
docker ps -a --filter "label=aiconnex-sandbox=true"
docker rm -f $(docker ps -aq --filter "label=aiconnex-sandbox=true")
```
