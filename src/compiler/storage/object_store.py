"""ObjectStore abstraction for immutable raw uploads and intermediate artifacts."""

from pathlib import Path
from typing import Protocol


class ObjectStore(Protocol):
    """Protocol for interacting with raw and transformed object storage."""

    def put(self, key: str, data: bytes) -> str:
        """Store raw bytes at key and return storage URI or path."""
        ...

    def get(self, key: str) -> bytes:
        """Retrieve bytes at key. Raises FileNotFoundError if missing."""
        ...

    def exists(self, key: str) -> bool:
        """Check whether object exists."""
        ...

    def delete(self, key: str) -> bool:
        """Delete object at key if present."""
        ...


class LocalFileSystemObjectStore:
    """Local filesystem-backed object store for development and testing."""

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, key: str) -> Path:
        clean_key = key.lstrip("/\\")
        target = (self.root_dir / clean_key).resolve()
        # Guard against path traversal
        if not str(target).startswith(str(self.root_dir.resolve())):
            raise ValueError(f"Path traversal detected: {key}")
        return target

    def put(self, key: str, data: bytes) -> str:
        target = self._resolve_path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return str(target)

    def get(self, key: str) -> bytes:
        target = self._resolve_path(key)
        if not target.is_file():
            raise FileNotFoundError(f"Object not found: {key}")
        return target.read_bytes()

    def exists(self, key: str) -> bool:
        target = self._resolve_path(key)
        return target.is_file()

    def delete(self, key: str) -> bool:
        target = self._resolve_path(key)
        if target.is_file():
            target.unlink()
            return True
        return False
