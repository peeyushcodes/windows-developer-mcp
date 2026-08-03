"""
Unit tests for ProjectProvider.
"""

from pathlib import Path

import pytest

from core.session import get_session, reset_session
from providers.project import ProjectProvider


@pytest.fixture(autouse=True)
def setup_session():
    reset_session()
    session = get_session()
    session.change_directory(str(Path.cwd()))
    yield


def test_project_analyze():
    provider = ProjectProvider()
    res = provider.project_analyze(".")
    assert res["status"] == "success"
    assert "project_types" in res["data"]
    assert "git" in res["data"]


def test_project_dependencies():
    provider = ProjectProvider()
    res = provider.project_dependencies(".")
    assert res["status"] == "success"
    assert "python" in res["data"]
    assert "nodejs" in res["data"]


def test_project_summarize():
    provider = ProjectProvider()
    res = provider.project_summarize(".", max_depth=1)
    assert res["status"] == "success"
    assert "tree" in res["data"]


def test_project_architecture():
    provider = ProjectProvider()
    res = provider.project_architecture(".")
    assert res["status"] == "success"
    assert "entry_points" in res["data"]
    assert "core_components" in res["data"]


def test_project_generate_readme():
    provider = ProjectProvider()
    res = provider.project_generate_readme(".")
    assert res["status"] == "success"
    assert "# " in res["data"]["readme_markdown"]


def test_project_generate_docs():
    provider = ProjectProvider()
    res = provider.project_generate_docs("core/config.py")
    assert res["status"] == "success"
    assert "classes" in res["data"]


def test_project_security_scan():
    provider = ProjectProvider()
    res = provider.project_security_scan(".")
    assert res["status"] == "success"
    assert "total_findings" in res["data"]


def test_project_generate_tests():
    provider = ProjectProvider()
    res = provider.project_generate_tests("core/config.py")
    assert res["status"] == "success"
    assert "test_code" in res["data"]
