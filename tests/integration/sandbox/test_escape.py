"""Real-container security and isolation verification tests for Phase 3 Docker sandbox."""

from __future__ import annotations

import pytest

import docker
from src.compiler.investigation.container_spec import HardenedContainerConfig


def _docker_available() -> bool:
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _docker_available(), reason="Docker daemon is not available")


def test_escape_network_egress():
    """Verify network egress is blocked (network_mode='none')."""
    client = docker.from_env()
    cfg = HardenedContainerConfig()
    # Attempt network request inside container — must fail with non-zero exit / URLError
    with pytest.raises(docker.errors.ContainerError) as exc_info:
        client.containers.run(
            image=cfg.image,
            command=[
                "python",
                "-c",
                "import urllib.request; urllib.request.urlopen('https://example.com', timeout=2)",
            ],
            network_mode=cfg.network_mode,
            user=cfg.user,
            read_only=cfg.read_only,
            cap_drop=list(cfg.cap_drop),
            detach=False,
            remove=True,
        )
    assert "Temporary failure in name resolution" in str(
        exc_info.value
    ) or "Network is unreachable" in str(exc_info.value)


def test_escape_write_to_rootfs():
    """Verify write to root filesystem is blocked (read_only=True)."""
    client = docker.from_env()
    cfg = HardenedContainerConfig()
    with pytest.raises(docker.errors.ContainerError) as exc_info:
        client.containers.run(
            image=cfg.image,
            command=["sh", "-c", "echo test > /test.txt"],
            network_mode=cfg.network_mode,
            user=cfg.user,
            read_only=cfg.read_only,
            cap_drop=list(cfg.cap_drop),
            detach=False,
            remove=True,
        )
    assert "Read-only file system" in str(exc_info.value) or exc_info.value.exit_status != 0


def test_verify_non_root_user():
    """Verify container process runs as uid:gid 1000:1000."""
    client = docker.from_env()
    cfg = HardenedContainerConfig()
    output = client.containers.run(
        image=cfg.image,
        command=["id", "-u"],
        network_mode=cfg.network_mode,
        user=cfg.user,
        read_only=cfg.read_only,
        cap_drop=list(cfg.cap_drop),
        detach=False,
        remove=True,
    )
    assert output.strip() == b"1000"


def test_escape_pids_limit():
    """Verify pids_limit prevents fork bomb denial of service."""
    client = docker.from_env()
    cfg = HardenedContainerConfig(pids_limit=16)
    with pytest.raises(docker.errors.ContainerError):
        client.containers.run(
            image=cfg.image,
            command=["python", "-c", "import os; [os.fork() for _ in range(50)]"],
            network_mode=cfg.network_mode,
            user=cfg.user,
            read_only=cfg.read_only,
            cap_drop=list(cfg.cap_drop),
            pids_limit=cfg.pids_limit,
            detach=False,
            remove=True,
        )
