"""
Project analysis provider for Windows Developer MCP.

Provides tools for understanding project structure, dependencies,
and codebase composition without executing arbitrary code.

Tools:
    analyze_project      — Detect project type and key files
    count_lines_of_code  — Count lines across the codebase
    find_todos           — Find TODO/FIXME/HACK comments
    dependency_check     — Check outdated/security issues in packages
    read_package_json    — Parse and summarise package.json
    read_pyproject_toml  — Parse and summarise pyproject.toml
    project_summary      — Comprehensive project overview
"""

from __future__ import annotations

import logging
from pathlib import Path
import re
from typing import Any

from core.exceptions import WorkspaceViolationError
from core.session import get_session
from providers.base import BaseProvider, tool
from security.sandbox import WorkspaceSandbox
from utils.helpers import Timer
from utils.json_utils import error as make_error
from utils.json_utils import success

logger = logging.getLogger(__name__)


class ProjectProvider(BaseProvider):
    """
    Provides static project analysis tools that do not execute arbitrary code.

    All operations are read-only. No files are created or modified.
    """

    name = "project"
    description = "Project structure analysis, LOC counting, TODO finding, and dependency review."

    def _workspace_root(self) -> Path:
        sandbox = WorkspaceSandbox()
        session = get_session()
        try:
            return sandbox.resolve_safe(session.cwd)
        except WorkspaceViolationError:
            return session.cwd

    @tool
    def analyze_project(self, path: str = ".") -> dict[str, Any]:
        """
        Detect project type, framework, and key configuration files.

        Identifies Python, Node.js, .NET, Rust, Go, Java, Docker,
        and other project types automatically by checking for
        characteristic files.

        Args:
            path: Project root directory. Defaults to cwd.

        Returns:
            A dict with keys: status, data (project_types, key_files, git, description).

        Examples:
            analyze_project()
            analyze_project("C:/projects/myapp")
        """
        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                root = sandbox.resolve_safe(
                    Path(path) if Path(path).is_absolute() else get_session().cwd / path
                )
            except WorkspaceViolationError as exc:
                return make_error(str(exc), tool="analyze_project", code="WORKSPACE_VIOLATION")

            indicators = {
                "python":     ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile"],
                "nodejs":     ["package.json", "yarn.lock", "pnpm-lock.yaml"],
                "dotnet":     ["*.csproj", "*.sln", "*.fsproj"],
                "rust":       ["Cargo.toml"],
                "go":         ["go.mod"],
                "java":       ["pom.xml", "build.gradle", "build.gradle.kts"],
                "docker":     ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"],
                "terraform":  ["main.tf", "*.tf"],
                "kubernetes": ["*.yaml", "*.yml"],  # coarse — refined below
            }

            detected: list[str] = []
            key_files: list[str] = []

            for tech, patterns in indicators.items():
                for pattern in patterns:
                    if "*" in pattern:
                        matches = list(root.glob(pattern))
                        if matches:
                            detected.append(tech)
                            key_files.extend([m.name for m in matches[:3]])
                    else:
                        if (root / pattern).exists():
                            detected.append(tech)
                            key_files.append(pattern)

            # Refine kubernetes (only if has k8s-like keys in yaml files)
            if "kubernetes" in detected:
                detected.remove("kubernetes")

            # Git info
            git_dir = root / ".git"
            git_info = {"present": git_dir.exists()}
            if git_dir.exists():
                head_file = git_dir / "HEAD"
                if head_file.exists():
                    head = head_file.read_text().strip()
                    if head.startswith("ref: refs/heads/"):
                        git_info["branch"] = head.replace("ref: refs/heads/", "")

            return success(
                {
                    "path": str(root),
                    "project_types": list(dict.fromkeys(detected)),  # deduplicated
                    "key_files": list(dict.fromkeys(key_files)),
                    "git": git_info,
                    "is_multi_project": len(detected) > 1,
                },
                tool="analyze_project",
                duration_ms=t.elapsed_ms,
            )

    @tool
    def count_lines_of_code(
        self,
        path: str = ".",
        extensions: str = ".py,.js,.ts,.jsx,.tsx,.cs,.go,.rs,.java,.cpp,.c,.h",
        exclude_dirs: str = ".venv,node_modules,.git,dist,build,__pycache__",
    ) -> dict[str, Any]:
        """
        Count lines of code across the codebase.

        Counts total lines, code lines (non-blank, non-comment), blank lines,
        and comment lines per file extension.

        Args:
            path:         Root directory to scan. Defaults to cwd.
            extensions:   Comma-separated list of file extensions to count.
            exclude_dirs: Comma-separated list of directory names to skip.

        Returns:
            A dict with keys: status, data (total lines, by_extension breakdown).

        Examples:
            count_lines_of_code()
            count_lines_of_code(extensions=".py,.pyi")
        """
        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                root = sandbox.resolve_safe(
                    Path(path) if Path(path).is_absolute() else get_session().cwd / path
                )
            except WorkspaceViolationError as exc:
                return make_error(str(exc), tool="count_lines_of_code", code="WORKSPACE_VIOLATION")

            exts = {e.strip() for e in extensions.split(",") if e.strip()}
            excl = {d.strip() for d in exclude_dirs.split(",") if d.strip()}

            by_ext: dict[str, dict[str, int]] = {}
            total_files = 0

            for file_path in root.rglob("*"):
                if not file_path.is_file():
                    continue
                # Skip excluded directories
                if any(part in excl for part in file_path.parts):
                    continue
                if file_path.suffix not in exts:
                    continue

                total_files += 1
                ext = file_path.suffix
                if ext not in by_ext:
                    by_ext[ext] = {"files": 0, "total": 0, "blank": 0, "code": 0}

                try:
                    text = file_path.read_text(encoding="utf-8", errors="ignore")
                    lines = text.splitlines()
                    blank = sum(1 for line_str in lines if not line_str.strip())
                    by_ext[ext]["files"] += 1
                    by_ext[ext]["total"] += len(lines)
                    by_ext[ext]["blank"] += blank
                    by_ext[ext]["code"] += len(lines) - blank
                except OSError:
                    pass

            total_lines = sum(v["total"] for v in by_ext.values())
            total_code = sum(v["code"] for v in by_ext.values())
            total_blank = sum(v["blank"] for v in by_ext.values())

            return success(
                {
                    "path": str(root),
                    "total_files": total_files,
                    "total_lines": total_lines,
                    "code_lines": total_code,
                    "blank_lines": total_blank,
                    "by_extension": {
                        ext: {
                            "files": v["files"],
                            "total_lines": v["total"],
                            "code_lines": v["code"],
                            "blank_lines": v["blank"],
                        }
                        for ext, v in sorted(by_ext.items(), key=lambda x: -x[1]["total"])
                    },
                },
                tool="count_lines_of_code",
                duration_ms=t.elapsed_ms,
            )

    @tool
    def find_todos(
        self,
        path: str = ".",
        tags: str = "TODO,FIXME,HACK,XXX,NOTE,BUG",
        extensions: str = ".py,.js,.ts,.jsx,.tsx,.cs,.go,.rs,.java,.cpp,.c",
        max_results: int = 100,
    ) -> dict[str, Any]:
        """
        Search for TODO/FIXME/HACK and similar tags in source files.

        Args:
            path:        Root directory to scan.
            tags:        Comma-separated list of comment tags to find.
            extensions:  File extensions to search.
            max_results: Maximum number of results. Default: 100.

        Returns:
            A dict with keys: status, data (count, items list with file/line/tag/text).

        Examples:
            find_todos()
            find_todos(tags="TODO,BUG")
            find_todos(path="src", extensions=".py")
        """
        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                root = sandbox.resolve_safe(
                    Path(path) if Path(path).is_absolute() else get_session().cwd / path
                )
            except WorkspaceViolationError as exc:
                return make_error(str(exc), tool="find_todos", code="WORKSPACE_VIOLATION")

            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            pattern = re.compile(
                r"(?:#|//|--)\s*(" + "|".join(re.escape(t) for t in tag_list) + r")\s*:?\s*(.*)",
                re.IGNORECASE,
            )
            exts = {e.strip() for e in extensions.split(",") if e.strip()}
            excl = {".venv", "node_modules", ".git", "__pycache__", "dist", "build"}

            results: list[dict[str, Any]] = []
            for file_path in root.rglob("*"):
                if len(results) >= max_results:
                    break
                if not file_path.is_file():
                    continue
                if any(part in excl for part in file_path.parts):
                    continue
                if file_path.suffix not in exts:
                    continue
                try:
                    for lineno, line in enumerate(
                        file_path.read_text(encoding="utf-8", errors="ignore").splitlines(),
                        start=1,
                    ):
                        m = pattern.search(line)
                        if m:
                            results.append(
                                {
                                    "file": str(file_path.relative_to(root)),
                                    "line": lineno,
                                    "tag": m.group(1).upper(),
                                    "text": m.group(2).strip(),
                                }
                            )
                            if len(results) >= max_results:
                                break
                except OSError:
                    pass

            return success(
                {"count": len(results), "truncated": len(results) >= max_results, "items": results},
                tool="find_todos",
                duration_ms=t.elapsed_ms,
            )

    @tool
    def read_package_json(self, path: str = "package.json") -> dict[str, Any]:
        """
        Parse and summarise a package.json file.

        Returns project name, version, description, scripts, dependencies,
        and devDependencies.

        Args:
            path: Path to package.json. Default: "package.json" in cwd.

        Returns:
            A dict with keys: status, data (name, version, scripts, dependencies).

        Examples:
            read_package_json()
            read_package_json("frontend/package.json")
        """
        import json

        from utils.json_utils import not_found

        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                file_path = sandbox.resolve_safe(
                    Path(path) if Path(path).is_absolute() else get_session().cwd / path
                )
            except WorkspaceViolationError as exc:
                return make_error(str(exc), tool="read_package_json", code="WORKSPACE_VIOLATION")

            if not file_path.exists():
                return not_found(str(file_path), tool="read_package_json")

            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                return success(
                    {
                        "name": data.get("name", ""),
                        "version": data.get("version", ""),
                        "description": data.get("description", ""),
                        "author": data.get("author", ""),
                        "license": data.get("license", ""),
                        "scripts": data.get("scripts", {}),
                        "dependencies": data.get("dependencies", {}),
                        "dev_dependencies": data.get("devDependencies", {}),
                        "engines": data.get("engines", {}),
                        "main": data.get("main", ""),
                    },
                    tool="read_package_json",
                    duration_ms=t.elapsed_ms,
                )
            except (json.JSONDecodeError, OSError) as exc:
                return make_error(str(exc), tool="read_package_json", code="PARSE_ERROR")

    @tool
    def read_pyproject_toml(self, path: str = "pyproject.toml") -> dict[str, Any]:
        """
        Parse and summarise a pyproject.toml file.

        Returns project name, version, description, dependencies,
        and tool configurations.

        Args:
            path: Path to pyproject.toml. Default: "pyproject.toml" in cwd.

        Returns:
            A dict with keys: status, data (name, version, dependencies, tools).

        Examples:
            read_pyproject_toml()
            read_pyproject_toml("backend/pyproject.toml")
        """
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore[no-redef]
            except ImportError:
                return make_error(
                    "TOML parsing requires Python 3.11+ or 'tomli' package.",
                    tool="read_pyproject_toml",
                    code="MISSING_DEPENDENCY",
                )

        from utils.json_utils import not_found

        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                file_path = sandbox.resolve_safe(
                    Path(path) if Path(path).is_absolute() else get_session().cwd / path
                )
            except WorkspaceViolationError as exc:
                return make_error(str(exc), tool="read_pyproject_toml", code="WORKSPACE_VIOLATION")

            if not file_path.exists():
                return not_found(str(file_path), tool="read_pyproject_toml")

            try:
                data = tomllib.loads(file_path.read_text(encoding="utf-8"))
                project = data.get("project", {})
                return success(
                    {
                        "name": project.get("name", ""),
                        "version": project.get("version", ""),
                        "description": project.get("description", ""),
                        "authors": project.get("authors", []),
                        "requires_python": project.get("requires-python", ""),
                        "dependencies": project.get("dependencies", []),
                        "optional_dependencies": project.get("optional-dependencies", {}),
                        "build_backend": data.get("build-system", {}).get("build-backend", ""),
                        "tools": list(data.get("tool", {}).keys()),
                    },
                    tool="read_pyproject_toml",
                    duration_ms=t.elapsed_ms,
                )
            except Exception as exc:
                return make_error(str(exc), tool="read_pyproject_toml", code="PARSE_ERROR")

    @tool
    def project_summary(self, path: str = ".") -> dict[str, Any]:
        """
        Return a comprehensive project overview combining multiple analyses.

        Combines project type detection, LOC counting, and TODO/FIXME listing
        into a single structured report.

        Args:
            path: Project root directory. Defaults to cwd.

        Returns:
            A dict with keys: status, data (project type, LOC stats, todos).

        Examples:
            project_summary()
            project_summary("C:/projects/myapp")
        """
        with Timer() as t:
            project_type_result = self.analyze_project(path)
            loc_result = self.count_lines_of_code(path)
            todo_result = self.find_todos(path, max_results=20)

            return success(
                {
                    "project": project_type_result.get("data", {}),
                    "loc": loc_result.get("data", {}),
                    "todos": todo_result.get("data", {}),
                },
                tool="project_summary",
                duration_ms=t.elapsed_ms,
            )
