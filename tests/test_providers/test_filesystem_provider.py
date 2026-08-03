"""Unit tests for FilesystemProvider."""

from pathlib import Path

import pytest

from core.session import get_session, reset_session
from providers.filesystem import FilesystemProvider


@pytest.fixture(autouse=True)
def setup_session():
    reset_session()
    session = get_session()
    session.change_directory(str(Path.cwd()))
    yield


class TestFilesystemProvider:
    def test_read_write_file(self):
        provider = FilesystemProvider()
        test_file = "test_rw_file.txt"
        try:
            write_res = provider.write_file(test_file, "Hello Filesystem!", confirm=True)
            assert write_res["status"] == "success"

            read_res = provider.read_file(test_file)
            assert read_res["status"] == "success"
            assert "Hello Filesystem!" in read_res["data"]["content"]
        finally:
            p = Path.cwd() / test_file
            if p.exists():
                p.unlink()

    def test_file_exists(self):
        provider = FilesystemProvider()
        test_file = "test_exists_file.txt"
        try:
            provider.write_file(test_file, "content", confirm=True)
            res_exists = provider.file_exists(test_file)
            assert res_exists["data"]["exists"] is True

            res_missing = provider.file_exists("missing_nonexistent_file.txt")
            assert res_missing["data"]["exists"] is False
        finally:
            p = Path.cwd() / test_file
            if p.exists():
                p.unlink()

    def test_list_directory_and_tree(self):
        provider = FilesystemProvider()
        list_res = provider.list_directory(".")
        assert list_res["status"] == "success"
        assert list_res["data"]["count"] >= 1

        tree_res = provider.tree(".", max_depth=2)
        assert tree_res["status"] == "success"

    def test_search_files(self):
        provider = FilesystemProvider()
        res = provider.search_files(".", pattern="*.py")
        assert res["status"] == "success"
        assert res["data"]["count"] >= 1

    def test_file_info(self):
        provider = FilesystemProvider()
        res = provider.file_info("server.py")
        assert res["status"] == "success"
        assert "size_bytes" in res["data"]
