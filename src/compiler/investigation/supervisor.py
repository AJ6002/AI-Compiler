"""Host-side supervisor managing hardened Docker container lifecycles and validation bridges."""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from docker.errors import DockerException

import docker
from src.compiler.contracts.client import ClientContract
from src.compiler.contracts.enums import JobResultState
from src.compiler.contracts.investigation import InvestigationResult, UnresolvedIssue
from src.compiler.contracts.plans import ParsePlan
from src.compiler.contracts.validation import PlanValidationReport
from src.compiler.investigation.container_spec import HardenedContainerConfig
from src.compiler.investigation.contract import unwrap_for_executor
from src.compiler.structure.types import DiscoveredLayout
from src.compiler.validation.plan_validator import PlanValidator

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SandboxMetadata:
    """Audit telemetry captured from sandbox execution."""

    image_digest: str
    container_id: str
    exit_code: int
    wall_clock_seconds: float
    timed_out: bool
    killed: bool
    logs: str = ""


@dataclass(frozen=True)
class SandboxOutcome:
    """Immutable supervisor verdict on the sandbox run."""

    status: Literal["PLAN_VALIDATED", "REVIEW_REQUIRED", "SANDBOX_FAILED"]
    investigation_result: InvestigationResult | None
    plan_validation_report: PlanValidationReport | None
    unresolved: list[UnresolvedIssue]
    failure_reason: (
        Literal[
            "TIMEOUT",
            "NO_OUTPUT",
            "CONTRACT_VIOLATION",
            "CONTAINER_ERROR",
            "DOCKER_UNAVAILABLE",
        ]
        | None
    )
    metadata: SandboxMetadata


class SandboxSupervisor:
    """Supervises isolated container execution, extracting output and enforcing validation."""

    def __init__(
        self,
        image: str = "aiconnex-sandbox:latest",
        plan_validator: PlanValidator | None = None,
        timeout_s: int = 90,
        runtime: str | None = None,
        docker_client: docker.DockerClient | None = None,
    ) -> None:
        self.image = image
        self.plan_validator = plan_validator or PlanValidator()
        self.timeout_s = timeout_s
        self.runtime = runtime
        self._docker_client = docker_client

    def _get_client(self) -> docker.DockerClient:
        if self._docker_client is not None:
            return self._docker_client
        try:
            return docker.from_env()
        except DockerException as exc:
            raise RuntimeError(f"Docker daemon is not available: {exc}") from exc

    def investigate(
        self,
        brief_data: dict[str, Any],
        workbook_bytes: bytes,
        workbook_filename: str = "workbook.xlsx",
        agent_script: str | None = None,
        contract: ClientContract | None = None,
        layout: DiscoveredLayout | None = None,
        default_asset_id: str = "DEFAULT_ASSET",
    ) -> SandboxOutcome:
        """Execute investigation inside a hardened container and validate output."""
        start_time = time.monotonic()
        temp_input = Path(tempfile.mkdtemp(prefix="aiconnex_sandbox_in_"))
        temp_output = Path(tempfile.mkdtemp(prefix="aiconnex_sandbox_out_"))

        container = None
        timed_out = False
        killed = False
        exit_code = -1
        container_id = "unknown"
        image_digest = "unknown"
        container_logs = ""

        try:
            # 1. Prepare /input files
            brief_file = temp_input / "brief.json"
            with open(brief_file, "w", encoding="utf-8") as f:
                json.dump(brief_data, f, indent=2)

            workbook_file = temp_input / workbook_filename
            with open(workbook_file, "wb") as f:
                f.write(workbook_bytes)

            script_file = temp_input / "run_agent.py"
            if agent_script:
                with open(script_file, "w", encoding="utf-8") as f:
                    f.write(agent_script)
            else:
                default_script = (
                    Path(__file__).resolve().parents[3] / "docker" / "sandbox" / "run_agent.py"
                )
                if default_script.exists():
                    shutil.copyfile(default_script, script_file)
                else:
                    # Fallback inline runner
                    with open(script_file, "w", encoding="utf-8") as f:
                        f.write(
                            "import json\nwith open('/output/result.json', 'w') as f:\n"
                            "  f.write('{}')\n"
                        )

            # 2. Configure container
            client = self._get_client()
            cfg = HardenedContainerConfig(
                image=self.image,
                runtime=self.runtime,
            )
            # Docker on Windows requires host path formatting for bind mounts
            in_mount = str(temp_input.resolve())
            out_mount = str(temp_output.resolve())
            kwargs = cfg.to_docker_kwargs(input_dir=in_mount, output_dir=out_mount)

            # 3. Create & start container
            container = client.containers.create(**kwargs)
            container_id = container.id
            image_digest = container.image.id if hasattr(container, "image") else self.image
            container.start()

            # 4. Wait with wall-clock timeout
            poll_interval = 0.5
            elapsed = 0.0
            while elapsed < self.timeout_s:
                container.reload()
                if container.status != "running":
                    break
                time.sleep(poll_interval)
                elapsed = time.monotonic() - start_time

            container.reload()
            if container.status == "running":
                # Timeout triggered -> SIGTERM then SIGKILL
                timed_out = True
                killed = True
                try:
                    container.stop(timeout=5)
                except Exception:
                    container.kill()
                exit_code = 137
            else:
                res = container.wait()
                exit_code = res.get("StatusCode", 0)

            try:
                container_logs = container.logs().decode("utf-8", errors="replace")
            except Exception:
                container_logs = ""

            wall_clock = time.monotonic() - start_time

            # 5. Process outcome
            if timed_out:
                meta = SandboxMetadata(
                    image_digest=image_digest,
                    container_id=container_id,
                    exit_code=exit_code,
                    wall_clock_seconds=wall_clock,
                    timed_out=True,
                    killed=True,
                    logs=container_logs,
                )
                return SandboxOutcome(
                    status="SANDBOX_FAILED",
                    investigation_result=None,
                    plan_validation_report=None,
                    unresolved=[],
                    failure_reason="TIMEOUT",
                    metadata=meta,
                )

            # 6. Read /output/result.json
            result_file = temp_output / "result.json"
            if not result_file.exists():
                meta = SandboxMetadata(
                    image_digest=image_digest,
                    container_id=container_id,
                    exit_code=exit_code,
                    wall_clock_seconds=wall_clock,
                    timed_out=False,
                    killed=False,
                    logs=container_logs,
                )
                return SandboxOutcome(
                    status="SANDBOX_FAILED",
                    investigation_result=None,
                    plan_validation_report=None,
                    unresolved=[],
                    failure_reason="NO_OUTPUT",
                    metadata=meta,
                )

            try:
                raw_json = result_file.read_text(encoding="utf-8")
                inv_result = InvestigationResult.model_validate_json(raw_json)
            except Exception as exc:
                logger.error(f"Failed to validate InvestigationResult JSON: {exc}")
                raw_snippet = raw_json[:200] if "raw_json" in locals() else "None"
                meta = SandboxMetadata(
                    image_digest=image_digest,
                    container_id=container_id,
                    exit_code=exit_code,
                    wall_clock_seconds=wall_clock,
                    timed_out=False,
                    killed=False,
                    logs=f"Contract validation error: {exc}\nRaw: {raw_snippet}",
                )
                return SandboxOutcome(
                    status="SANDBOX_FAILED",
                    investigation_result=None,
                    plan_validation_report=None,
                    unresolved=[],
                    failure_reason="CONTRACT_VIOLATION",
                    metadata=meta,
                )

            # 7. Check InvestigationResult status
            if inv_result.status == "REVIEW_REQUIRED":
                meta = SandboxMetadata(
                    image_digest=image_digest,
                    container_id=container_id,
                    exit_code=exit_code,
                    wall_clock_seconds=wall_clock,
                    timed_out=False,
                    killed=False,
                    logs=container_logs,
                )
                return SandboxOutcome(
                    status="REVIEW_REQUIRED",
                    investigation_result=inv_result,
                    plan_validation_report=None,
                    unresolved=inv_result.unresolved,
                    failure_reason=None,
                    metadata=meta,
                )

            # 8. If status == PLAN_PROPOSED -> unwrap and validate via PlanValidator
            plan: ParsePlan = unwrap_for_executor(inv_result)
            val_rep = self.plan_validator.validate(
                plan=plan,
                source=workbook_bytes,
                contract=contract,
                layout=layout,
                source_filename=workbook_filename,
                default_asset_id=default_asset_id,
            )

            meta = SandboxMetadata(
                image_digest=image_digest,
                container_id=container_id,
                exit_code=exit_code,
                wall_clock_seconds=wall_clock,
                timed_out=False,
                killed=False,
                logs=container_logs,
            )

            if val_rep.status == JobResultState.ACCEPTED:
                return SandboxOutcome(
                    status="PLAN_VALIDATED",
                    investigation_result=inv_result,
                    plan_validation_report=val_rep,
                    unresolved=[],
                    failure_reason=None,
                    metadata=meta,
                )
            else:
                return SandboxOutcome(
                    status="REVIEW_REQUIRED",
                    investigation_result=inv_result,
                    plan_validation_report=val_rep,
                    unresolved=[],
                    failure_reason=None,
                    metadata=meta,
                )

        except DockerException as d_exc:
            wall_clock = time.monotonic() - start_time
            meta = SandboxMetadata(
                image_digest=image_digest,
                container_id=container_id,
                exit_code=exit_code,
                wall_clock_seconds=wall_clock,
                timed_out=False,
                killed=False,
                logs=str(d_exc),
            )
            return SandboxOutcome(
                status="SANDBOX_FAILED",
                investigation_result=None,
                plan_validation_report=None,
                unresolved=[],
                failure_reason="DOCKER_UNAVAILABLE",
                metadata=meta,
            )

        finally:
            # Container and temp directory cleanup
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:
                    pass
            shutil.rmtree(temp_input, ignore_errors=True)
            shutil.rmtree(temp_output, ignore_errors=True)
