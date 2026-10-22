"""Storage abstractions and local filesystem implementations."""

from src.compiler.storage.object_store import LocalFileSystemObjectStore, ObjectStore

__all__ = ["ObjectStore", "LocalFileSystemObjectStore"]
