"""
Shared pytest fixtures and configuration for Windows Developer MCP tests.

All tests run with:
- A fresh session scoped to the workspace root
- A test workspace directory (tests/fixtures/workspace/)
- Mocked config pointing at the test workspace
- Reset executor and session singletons between tests
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Test Workspace Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def workspace_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """
    A session-scoped temporary workspace directory.

    Shared across all tests in a test session. Contains a realistic
    set of starter files for integration tests.
    """
    root = tmp_path_factory.mktemp("workspace", numbered=False)

    # Create a minimal workspace structure
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text(
        '"""Main module."""\n\ndef main():\n    print("Hello")\n\n# TODO: add logging\n# FIXME: handle errors\n'
    )
    (root / "src" / "__init__.py").write_text("")
    (root / "tests").mkdir()
    (root / "data").mkdir()
    (root / "data" / "sample.db").write_bytes(b"")  # will be created properly in db tests
    (root / "README.md").write_text("# Test Project\n")
    (root / "requirements.txt").write_text("fastmcp\npydantic\n")
    (root / ".gitignore").write_text("__pycache__/\n*.pyc\n")

    return root


@pytest.fixture(autouse=True)
def reset_singletons(workspace_root: Path) -> None:
    """
    Reset session and executor singletons before every test.

    This ensures tests are fully isolated from each other.
    """
    from core.config import reset_config
    from core.executor import reset_executor
    from core.session import get_session, reset_session

    reset_config()
    reset_session()
    reset_executor()

    # Set session cwd to the test workspace
    session = get_session()
    session.change_directory(str(workspace_root))


@pytest.fixture()
def config_override(workspace_root: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Override configuration values for a single test.

    Returns a callable that accepts keyword overrides and applies them.
    """

    def _override(**kwargs):
        from core.config import get_config

        cfg = get_config()
        # Apply overrides via monkeypatching
        for key, value in kwargs.items():
            parts = key.split(".")
            obj = cfg
            for part in parts[:-1]:
                obj = getattr(obj, part)
            monkeypatch.setattr(obj, parts[-1], value, raising=False)

    return _override


@pytest.fixture()
def test_file(workspace_root: Path) -> Generator[Path, None, None]:
    """A temporary file in the workspace for read/write tests."""
    f = workspace_root / "test_file.txt"
    f.write_text("line 1\nline 2\nline 3\n")
    yield f
    if f.exists():
        f.unlink()


@pytest.fixture()
def test_db(workspace_root: Path) -> Generator[Path, None, None]:
    """A temporary SQLite database in the workspace."""
    import sqlite3

    db = workspace_root / "test.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)"
        )
        conn.execute("INSERT INTO users (name, email) VALUES ('Alice', 'alice@example.com')")
        conn.execute("INSERT INTO users (name, email) VALUES ('Bob', 'bob@example.com')")
        conn.commit()
    yield db
    if db.exists():
        db.unlink()
