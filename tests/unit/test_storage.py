import pytest

from src.compiler.storage.object_store import LocalFileSystemObjectStore


def test_local_object_store_crud(tmp_path):
    store = LocalFileSystemObjectStore(root_dir=tmp_path)
    test_key = "uploads/test_file.bin"
    test_data = b"raw binary spreadsheet upload content"

    # 1. Initially does not exist
    assert not store.exists(test_key)

    # 2. Put
    stored_path = store.put(test_key, test_data)
    assert stored_path is not None
    assert store.exists(test_key)

    # 3. Get
    retrieved = store.get(test_key)
    assert retrieved == test_data

    # 4. Delete
    assert store.delete(test_key) is True
    assert not store.exists(test_key)


def test_local_object_store_path_traversal(tmp_path):
    store = LocalFileSystemObjectStore(root_dir=tmp_path)
    with pytest.raises(ValueError, match="Path traversal detected"):
        store.put("../../../etc/passwd", b"malicious")
