"""
Filesystem provider for Windows Developer MCP.

Exposes safe, workspace-sandboxed file system operations as MCP tools.
Every path is validated against the workspace boundary before any
operation is performed.

Tools:
    read_file         — Read file contents
    write_file        — Create or overwrite a file
    append_file       — Append content to a file
    copy_file         — Copy a file
    move_file         — Move or rename a file
    delete_file       — Delete a file (requires confirmation)
    create_directory  — Create a directory tree
    list_directory    — List directory contents
    tree              — Directory tree view
    search_files      — Search for files by name pattern
    file_info         — File metadata (size, dates, permissions)
    file_exists       — Check if a path exists
"""

from __future__ import annotations

from datetime import UTC, datetime
import logging
import os
from pathlib import Path
import shutil
from typing import Any

from core.session import get_session
from providers.base import BaseProvider, tool
from security.sandbox import WorkspaceSandbox
from utils.helpers import Timer, format_size
from utils.json_utils import (
    confirmation_required,
    not_found,
    success,
)
from utils.json_utils import (
    error as make_error,
)

logger = logging.getLogger(__name__)


def _resolve(path: str, sandbox: WorkspaceSandbox) -> Path:
    """Resolve and sandbox-check a path relative to the session cwd."""
    session = get_session()
    raw = Path(path) if Path(path).is_absolute() else session.cwd / path
    return sandbox.resolve_safe(raw)


class FilesystemProvider(BaseProvider):
    """
    Provides safe, sandbox-enforced file system operations.

    All paths are resolved relative to the session's current working
    directory and then validated against the workspace sandbox. Paths
    that escape the workspace raise a ``WorkspaceViolationError`` and
    return a structured error response.
    """

    name = "filesystem"
    description = "Read, write, copy, move, delete, list, tree, and search files."

    # ------------------------------------------------------------------
    # Read Operations
    # ------------------------------------------------------------------

    @tool
    def read_file(
        self,
        path: str,
        encoding: str = "utf-8",
        max_bytes: int = 1_000_000,
    ) -> dict[str, Any]:
        """
        Read and return the contents of a text file.

        Args:
            path:      Path to the file (absolute or relative to cwd).
            encoding:  File encoding. Default: "utf-8".
            max_bytes: Maximum bytes to read. Larger files are truncated.
                       Default: 1,000,000 (1 MB).

        Returns:
            A dict with keys: status, data (content, size, encoding, truncated).

        Examples:
            read_file("README.md")
            read_file("C:/projects/app/config.json")
            read_file("src/main.py", max_bytes=50000)
        """
        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                file_path = _resolve(path, sandbox)
            except Exception as exc:
                return make_error(str(exc), tool="read_file", code="WORKSPACE_VIOLATION")

            if not file_path.exists():
                return not_found(f"File {file_path}", tool="read_file")
            if not file_path.is_file():
                return make_error(
                    f"{file_path} is not a file.", tool="read_file", code="NOT_A_FILE"
                )

            try:
                file_size = file_path.stat().st_size
                with open(file_path, encoding=encoding, errors="replace") as f:
                    content = f.read(max_bytes)
                truncated = file_size > max_bytes

                return success(
                    {
                        "path": str(file_path),
                        "content": content,
                        "size_bytes": file_size,
                        "encoding": encoding,
                        "truncated": truncated,
                        "lines": content.count("\n") + (1 if content else 0),
                    },
                    tool="read_file",
                    duration_ms=t.elapsed_ms,
                )
            except (OSError, UnicodeDecodeError) as exc:
                return make_error(str(exc), tool="read_file", code="READ_ERROR")

    @tool
    def file_info(self, path: str) -> dict[str, Any]:
        """
        Return metadata for a file or directory.

        Includes size, creation time, modification time, file type,
        and whether the path is readable/writable.

        Args:
            path: Path to the file or directory.

        Returns:
            A dict with keys: status, data (name, path, type, size, dates, permissions).

        Examples:
            file_info("README.md")
            file_info("C:/projects/myapp")
        """
        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                target = _resolve(path, sandbox)
            except Exception as exc:
                return make_error(str(exc), tool="file_info", code="WORKSPACE_VIOLATION")

            if not target.exists():
                return not_found(str(target), tool="file_info")

            try:
                stat = target.stat()
                return success(
                    {
                        "name": target.name,
                        "path": str(target),
                        "type": "directory" if target.is_dir() else "file",
                        "size_bytes": stat.st_size,
                        "size_human": format_size(stat.st_size),
                        "created": datetime.fromtimestamp(stat.st_ctime, tz=UTC).isoformat(),
                        "modified": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
                        "extension": target.suffix,
                        "readable": os.access(target, os.R_OK),
                        "writable": os.access(target, os.W_OK),
                    },
                    tool="file_info",
                    duration_ms=t.elapsed_ms,
                )
            except OSError as exc:
                return make_error(str(exc), tool="file_info", code="STAT_ERROR")

    @tool
    def file_exists(self, path: str) -> dict[str, Any]:
        """
        Check whether a path exists within the workspace.

        Args:
            path: The path to check.

        Returns:
            A dict with keys: status, data (exists, is_file, is_dir, path).

        Examples:
            file_exists("README.md")
            file_exists("C:/projects/myapp/.git")
        """
        sandbox = WorkspaceSandbox()
        try:
            target = _resolve(path, sandbox)
        except Exception as exc:
            return make_error(str(exc), tool="file_exists", code="WORKSPACE_VIOLATION")

        return success(
            {
                "path": str(target),
                "exists": target.exists(),
                "is_file": target.is_file(),
                "is_dir": target.is_dir(),
            },
            tool="file_exists",
        )

    @tool
    def list_directory(
        self,
        path: str = ".",
        show_hidden: bool = False,
    ) -> dict[str, Any]:
        """
        List the contents of a directory.

        Args:
            path:        Directory to list. Defaults to the current working directory.
            show_hidden: If True, include hidden files (names starting with ".").

        Returns:
            A dict with keys: status, data (path, entries list with name/type/size).

        Examples:
            list_directory()
            list_directory("C:/projects")
            list_directory("src", show_hidden=True)
        """
        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                dir_path = _resolve(path, sandbox)
            except Exception as exc:
                return make_error(str(exc), tool="list_directory", code="WORKSPACE_VIOLATION")

            if not dir_path.exists():
                return not_found(f"Directory {dir_path}", tool="list_directory")
            if not dir_path.is_dir():
                return make_error(
                    f"{dir_path} is not a directory.", tool="list_directory", code="NOT_A_DIR"
                )

            try:
                entries = []
                for item in sorted(dir_path.iterdir(), key=lambda p: (p.is_file(), p.name)):
                    if not show_hidden and item.name.startswith("."):
                        continue
                    stat = item.stat()
                    entries.append(
                        {
                            "name": item.name,
                            "type": "directory" if item.is_dir() else "file",
                            "size_bytes": stat.st_size if item.is_file() else None,
                            "size_human": format_size(stat.st_size) if item.is_file() else None,
                            "modified": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
                        }
                    )
                return success(
                    {"path": str(dir_path), "count": len(entries), "entries": entries},
                    tool="list_directory",
                    duration_ms=t.elapsed_ms,
                )
            except OSError as exc:
                return make_error(str(exc), tool="list_directory", code="LIST_ERROR")

    @tool
    def tree(
        self,
        path: str = ".",
        max_depth: int = 3,
        show_hidden: bool = False,
    ) -> dict[str, Any]:
        """
        Return a directory tree view up to a specified depth.

        Args:
            path:        Root directory for the tree. Defaults to cwd.
            max_depth:   Maximum depth to recurse (1–10). Default: 3.
            show_hidden: Include hidden files and directories.

        Returns:
            A dict with keys: status, data (tree string, file_count, dir_count).

        Examples:
            tree()
            tree("C:/projects/myapp", max_depth=4)
        """
        sandbox = WorkspaceSandbox()
        max_depth = max(1, min(max_depth, 10))
        with Timer() as t:
            try:
                root = _resolve(path, sandbox)
            except Exception as exc:
                return make_error(str(exc), tool="tree", code="WORKSPACE_VIOLATION")

            if not root.exists():
                return not_found(f"Directory {root}", tool="tree")

            lines: list[str] = [str(root)]
            file_count = 0
            dir_count = 0

            def _recurse(dir_path: Path, prefix: str, depth: int) -> None:
                nonlocal file_count, dir_count
                if depth > max_depth:
                    return
                try:
                    items = sorted(
                        dir_path.iterdir(),
                        key=lambda p: (p.is_file(), p.name.lower()),
                    )
                except PermissionError:
                    lines.append(f"{prefix}[Permission Denied]")
                    return

                visible = [i for i in items if show_hidden or not i.name.startswith(".")]
                for idx, item in enumerate(visible):
                    is_last = idx == len(visible) - 1
                    connector = "└── " if is_last else "├── "
                    extension = "    " if is_last else "│   "
                    if item.is_dir():
                        dir_count += 1
                        lines.append(f"{prefix}{connector}{item.name}/")
                        _recurse(item, prefix + extension, depth + 1)
                    else:
                        file_count += 1
                        size = format_size(item.stat().st_size)
                        lines.append(f"{prefix}{connector}{item.name} ({size})")

            _recurse(root, "", 1)
            lines.append(f"\n{dir_count} directories, {file_count} files")

            return success(
                {
                    "path": str(root),
                    "tree": "\n".join(lines),
                    "file_count": file_count,
                    "dir_count": dir_count,
                    "max_depth": max_depth,
                },
                tool="tree",
                duration_ms=t.elapsed_ms,
            )

    @tool
    def search_files(
        self,
        path: str = ".",
        pattern: str = "*",
        recursive: bool = True,
        max_results: int = 100,
    ) -> dict[str, Any]:
        """
        Search for files matching a glob pattern.

        Args:
            path:        Directory to search. Defaults to cwd.
            pattern:     Glob pattern (e.g. "*.py", "test_*.py", "config.*").
            recursive:   If True, search subdirectories. Default: True.
            max_results: Maximum number of results to return. Default: 100.

        Returns:
            A dict with keys: status, data (matches list, truncated bool, count).

        Examples:
            search_files(pattern="*.py")
            search_files("C:/projects", pattern="*.json")
            search_files(pattern="test_*.py", recursive=True)
        """
        sandbox = WorkspaceSandbox()
        max_results = max(1, min(max_results, 1000))
        with Timer() as t:
            try:
                root = _resolve(path, sandbox)
            except Exception as exc:
                return make_error(str(exc), tool="search_files", code="WORKSPACE_VIOLATION")

            if not root.exists():
                return not_found(f"Directory {root}", tool="search_files")

            matches: list[dict[str, Any]] = []
            try:
                iterator = root.rglob(pattern) if recursive else root.glob(pattern)

                for item in iterator:
                    if len(matches) >= max_results:
                        break
                    if item.is_file():
                        stat = item.stat()
                        matches.append(
                            {
                                "path": str(item),
                                "name": item.name,
                                "relative": str(item.relative_to(root)),
                                "size_bytes": stat.st_size,
                                "size_human": format_size(stat.st_size),
                            }
                        )

                return success(
                    {
                        "root": str(root),
                        "pattern": pattern,
                        "count": len(matches),
                        "truncated": len(matches) >= max_results,
                        "matches": matches,
                    },
                    tool="search_files",
                    duration_ms=t.elapsed_ms,
                )
            except Exception as exc:
                return make_error(str(exc), tool="search_files", code="SEARCH_ERROR")

    # ------------------------------------------------------------------
    # Write Operations
    # ------------------------------------------------------------------

    @tool
    def write_file(
        self,
        path: str,
        content: str,
        encoding: str = "utf-8",
        confirm: bool = False,
    ) -> dict[str, Any]:
        """
        Create or overwrite a file with the given content.

        Creates parent directories automatically. Overwrites existing files
        without warning — use file_exists() first if unsure.

        Requires explicit confirmation when ``security.require_confirmation``
        is enabled in config.

        Args:
            path:     Path to write (absolute or relative to cwd).
            content:  The text content to write.
            encoding: File encoding. Default: "utf-8".
            confirm:  Set to True to confirm when required by config.

        Returns:
            A dict with keys: status, data (path, size_bytes, lines).

        Examples:
            write_file("notes.txt", "Hello, World!")
            write_file("src/config.py", "DEBUG = True\n", confirm=True)
        """
        from core.exceptions import ConfirmationRequiredError
        from security.permissions import PermissionManager

        pm = PermissionManager()
        if pm.requires_confirmation("write_file"):
            try:
                pm.assert_confirmed(action=f"write_file({path!r})", confirm=confirm)
            except ConfirmationRequiredError:
                return confirmation_required(f"write_file({path!r})", tool="write_file")

        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                file_path = _resolve(path, sandbox)
            except Exception as exc:
                return make_error(str(exc), tool="write_file", code="WORKSPACE_VIOLATION")

            try:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content, encoding=encoding)
                return success(
                    {
                        "path": str(file_path),
                        "size_bytes": len(content.encode(encoding)),
                        "lines": content.count("\n") + (1 if content else 0),
                        "created": not file_path.exists(),
                    },
                    tool="write_file",
                    duration_ms=t.elapsed_ms,
                )
            except OSError as exc:
                return make_error(str(exc), tool="write_file", code="WRITE_ERROR")

    @tool
    def append_file(
        self,
        path: str,
        content: str,
        encoding: str = "utf-8",
    ) -> dict[str, Any]:
        """
        Append content to an existing file (or create it if it does not exist).

        Args:
            path:     Path to the file.
            content:  Content to append.
            encoding: File encoding. Default: "utf-8".

        Returns:
            A dict with keys: status, data (path, total_size_bytes).

        Examples:
            append_file("log.txt", "New entry\n")
            append_file("output.csv", "row1,row2\n")
        """
        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                file_path = _resolve(path, sandbox)
            except Exception as exc:
                return make_error(str(exc), tool="append_file", code="WORKSPACE_VIOLATION")

            try:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, "a", encoding=encoding) as f:
                    f.write(content)
                return success(
                    {
                        "path": str(file_path),
                        "total_size_bytes": file_path.stat().st_size,
                    },
                    tool="append_file",
                    duration_ms=t.elapsed_ms,
                )
            except OSError as exc:
                return make_error(str(exc), tool="append_file", code="WRITE_ERROR")

    @tool
    def create_directory(self, path: str) -> dict[str, Any]:
        """
        Create a directory and all necessary parent directories.

        Args:
            path: The directory path to create.

        Returns:
            A dict with keys: status, data (path, created bool).

        Examples:
            create_directory("src/components")
            create_directory("C:/projects/myapp/tests")
        """
        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                dir_path = _resolve(path, sandbox)
            except Exception as exc:
                return make_error(str(exc), tool="create_directory", code="WORKSPACE_VIOLATION")

            try:
                existed = dir_path.exists()
                dir_path.mkdir(parents=True, exist_ok=True)
                return success(
                    {"path": str(dir_path), "created": not existed},
                    tool="create_directory",
                    duration_ms=t.elapsed_ms,
                )
            except OSError as exc:
                return make_error(str(exc), tool="create_directory", code="CREATE_ERROR")

    @tool
    def copy_file(self, src: str, dst: str, confirm: bool = False) -> dict[str, Any]:
        """
        Copy a file to a new location within the workspace.

        Args:
            src:     Source file path.
            dst:     Destination file path.
            confirm: Set to True to confirm if destination already exists.

        Returns:
            A dict with keys: status, data (src, dst, size_bytes).

        Examples:
            copy_file("config.toml", "config.toml.bak")
            copy_file("src/main.py", "src/main_v2.py", confirm=True)
        """
        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                src_path = _resolve(src, sandbox)
                dst_path = _resolve(dst, sandbox)
            except Exception as exc:
                return make_error(str(exc), tool="copy_file", code="WORKSPACE_VIOLATION")

            if not src_path.exists():
                return not_found(f"Source file {src_path}", tool="copy_file")

            if dst_path.exists() and not confirm:
                from security.permissions import PermissionManager

                pm = PermissionManager()
                if pm.requires_confirmation("copy_file"):
                    return confirmation_required(
                        f"Overwrite existing file {dst_path}", tool="copy_file"
                    )

            try:
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dst_path)
                return success(
                    {
                        "src": str(src_path),
                        "dst": str(dst_path),
                        "size_bytes": dst_path.stat().st_size,
                    },
                    tool="copy_file",
                    duration_ms=t.elapsed_ms,
                )
            except OSError as exc:
                return make_error(str(exc), tool="copy_file", code="COPY_ERROR")

    @tool
    def move_file(self, src: str, dst: str, confirm: bool = False) -> dict[str, Any]:
        """
        Move or rename a file within the workspace.

        Args:
            src:     Source path.
            dst:     Destination path.
            confirm: Set to True to confirm when required by config.

        Returns:
            A dict with keys: status, data (src, dst).

        Examples:
            move_file("draft.md", "README.md", confirm=True)
            move_file("old_name.py", "new_name.py", confirm=True)
        """
        from core.exceptions import ConfirmationRequiredError
        from security.permissions import PermissionManager

        pm = PermissionManager()
        if pm.requires_confirmation("move_file"):
            try:
                pm.assert_confirmed(action=f"move_file({src!r} → {dst!r})", confirm=confirm)
            except ConfirmationRequiredError:
                return confirmation_required(f"move_file({src!r} → {dst!r})", tool="move_file")

        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                src_path = _resolve(src, sandbox)
                dst_path = _resolve(dst, sandbox)
            except Exception as exc:
                return make_error(str(exc), tool="move_file", code="WORKSPACE_VIOLATION")

            if not src_path.exists():
                return not_found(f"Source {src_path}", tool="move_file")

            try:
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src_path), str(dst_path))
                return success(
                    {"src": str(src_path), "dst": str(dst_path)},
                    tool="move_file",
                    duration_ms=t.elapsed_ms,
                )
            except OSError as exc:
                return make_error(str(exc), tool="move_file", code="MOVE_ERROR")

    @tool
    def delete_file(self, path: str, confirm: bool = False) -> dict[str, Any]:
        """
        Permanently delete a file from the workspace.

        This operation is irreversible. Requires explicit confirmation
        when ``security.require_confirmation`` is enabled (default: True).

        Args:
            path:    Path to the file to delete.
            confirm: Set to True to confirm this destructive operation.

        Returns:
            A dict with keys: status, data (path, deleted bool).

        Examples:
            delete_file("temp.txt", confirm=True)
            delete_file("old_config.json", confirm=True)
        """
        from core.exceptions import ConfirmationRequiredError
        from security.permissions import PermissionManager

        pm = PermissionManager()
        if pm.requires_confirmation("delete_file"):
            try:
                pm.assert_confirmed(action=f"delete_file({path!r})", confirm=confirm)
            except ConfirmationRequiredError:
                return confirmation_required(f"delete_file({path!r})", tool="delete_file")

        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                file_path = _resolve(path, sandbox)
            except Exception as exc:
                return make_error(str(exc), tool="delete_file", code="WORKSPACE_VIOLATION")

            if not file_path.exists():
                return not_found(f"File {file_path}", tool="delete_file")
            if file_path.is_dir():
                return make_error(
                    f"{file_path} is a directory. Use a directory removal tool.",
                    tool="delete_file",
                    code="IS_DIRECTORY",
                )

            try:
                file_path.unlink()
                return success(
                    {"path": str(file_path), "deleted": True},
                    tool="delete_file",
                    duration_ms=t.elapsed_ms,
                )
            except OSError as exc:
                return make_error(str(exc), tool="delete_file", code="DELETE_ERROR")
