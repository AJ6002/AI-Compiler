"""Hardened container specifications and security policies for untrusted workbook investigation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HardenedContainerConfig:
    """Security and cgroup limits enforced on the sandbox container."""

    image: str = "aiconnex-sandbox:latest"
    network_mode: str = "none"
    user: str = "1000:1000"
    read_only: bool = True
    cap_drop: tuple[str, ...] = ("ALL",)
    security_opt: tuple[str, ...] = ("no-new-privileges:true",)
    pids_limit: int = 64
    mem_limit: str = "512m"
    memswap_limit: str = "512m"
    nano_cpus: int = 1_000_000_000  # 1 CPU core
    runtime: str | None = None  # "runsc" when gVisor enabled

    def to_docker_kwargs(
        self,
        input_dir: str,
        output_dir: str,
        command: list[str] | None = None,
    ) -> dict[str, Any]:
        """Convert security configurations into kwargs for docker.containers.create."""
        kwargs: dict[str, Any] = {
            "image": self.image,
            "command": command or ["python", "/input/run_agent.py"],
            "network_mode": self.network_mode,
            "user": self.user,
            "read_only": self.read_only,
            "cap_drop": list(self.cap_drop),
            "security_opt": list(self.security_opt),
            "pids_limit": self.pids_limit,
            "mem_limit": self.mem_limit,
            "memswap_limit": self.memswap_limit,
            "nano_cpus": self.nano_cpus,
            "volumes": {
                input_dir: {"bind": "/input", "mode": "ro"},
                output_dir: {"bind": "/output", "mode": "rw"},
            },
            "tmpfs": {
                "/tmp": "size=64m",
                "/work": "size=256m",
            },
            "detach": True,
            "labels": {"aiconnex-sandbox": "true"},
        }
        if self.runtime:
            kwargs["runtime"] = self.runtime
        return kwargs
