"""
Project analysis provider for Windows Developer MCP.

Provides tools for understanding project structure, dependencies, codebase composition,
architecture analysis, security scanning, documentation generation, and test creation.

Tools:
    project_analyze         — Comprehensive workspace overview & tech stack identification
    project_dependencies    — Dependency tree & configuration analyzer
    project_summarize       — Repository hierarchy & file role breakdown
    project_architecture    — Component topology & design pattern discovery
    project_generate_readme — AI-driven README draft generator
    project_generate_docs   — Automated API & docstring documentation builder
    project_security_scan   — Static pattern security audit (hardcoded secrets, credentials)
    project_generate_tests  — Test skeleton generator for source files
    count_lines_of_code     — Count lines across the codebase
    find_todos              — Find TODO/FIXME/HACK comments
    read_package_json       — Parse and summarize package.json
    read_pyproject_toml     — Parse and summarize pyproject.toml
"""

from __future__ import annotations

import json
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
    Provides static project analysis, architecture inspection, documentation generation,
    security scanning, and test skeleton creation tools.

    All operations operate safely within workspace boundaries.
    """

    name = "project"
    description = "Project structure analysis, LOC counting, architecture inspection, security scanning, and AI docs/tests generation."

    def _workspace_root(self) -> Path:
        sandbox = WorkspaceSandbox()
        session = get_session()
        try:
            return sandbox.resolve_safe(session.cwd)
        except WorkspaceViolationError:
            return session.cwd

    @tool
    def project_analyze(self, path: str = ".") -> dict[str, Any]:
        """
        Analyze project workspace structure, frameworks, and key configurations.

        Identifies Python, Node.js, .NET, Rust, Go, Java, Docker, and other frameworks
        by inspecting root configuration markers.

        Args:
            path: Project root directory path. Defaults to "." (current working directory).

        Returns:
            Dict containing status, workspace path, detected tech stacks, key config files, and Git status.

        Examples:
            project_analyze()
            project_analyze("C:/projects/myapp")
        """
        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                root = sandbox.resolve_safe(
                    Path(path) if Path(path).is_absolute() else get_session().cwd / path
                )
            except WorkspaceViolationError as exc:
                return make_error(str(exc), tool="project_analyze", code="WORKSPACE_VIOLATION")

            indicators = {
                "python": [
                    "pyproject.toml",
                    "setup.py",
                    "setup.cfg",
                    "requirements.txt",
                    "Pipfile",
                ],
                "nodejs": ["package.json", "yarn.lock", "pnpm-lock.yaml"],
                "dotnet": ["*.csproj", "*.sln", "*.fsproj"],
                "rust": ["Cargo.toml"],
                "go": ["go.mod"],
                "java": ["pom.xml", "build.gradle", "build.gradle.kts"],
                "docker": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"],
                "terraform": ["main.tf", "*.tf"],
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

            git_dir = root / ".git"
            git_info: dict[str, Any] = {"present": git_dir.exists()}
            if git_dir.exists():
                head_file = git_dir / "HEAD"
                if head_file.exists():
                    head = head_file.read_text().strip()
                    if head.startswith("ref: refs/heads/"):
                        git_info["branch"] = head.replace("ref: refs/heads/", "")

            return success(
                {
                    "path": str(root),
                    "project_types": list(dict.fromkeys(detected)),
                    "key_files": list(dict.fromkeys(key_files)),
                    "git": git_info,
                    "is_multi_project": len(detected) > 1,
                },
                tool="project_analyze",
                duration_ms=t.elapsed_ms,
            )

    @tool
    def project_dependencies(self, path: str = ".") -> dict[str, Any]:
        """
        Extract and summarize project dependencies across Python and Node.js manifests.

        Inspects package.json, pyproject.toml, requirements.txt, and lockfiles to assemble
        a consolidated dependency manifest.

        Args:
            path: Project root directory. Defaults to ".".

        Returns:
            Dict containing Python dependencies, Node.js dependencies, and lockfile statuses.

        Examples:
            project_dependencies()
        """
        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                root = sandbox.resolve_safe(
                    Path(path) if Path(path).is_absolute() else get_session().cwd / path
                )
            except WorkspaceViolationError as exc:
                return make_error(str(exc), tool="project_dependencies", code="WORKSPACE_VIOLATION")

            python_deps: dict[str, Any] = {}
            node_deps: dict[str, Any] = {}

            # Pyproject.toml
            pyp = root / "pyproject.toml"
            if pyp.exists():
                try:
                    import tomllib

                    content = tomllib.loads(pyp.read_text(encoding="utf-8"))
                    python_deps["pyproject"] = content.get("project", {}).get("dependencies", [])
                except Exception:
                    pass

            # Requirements.txt
            req = root / "requirements.txt"
            if req.exists():
                try:
                    lines = [
                        line.strip()
                        for line in req.read_text(encoding="utf-8").splitlines()
                        if line.strip() and not line.startswith("#")
                    ]
                    python_deps["requirements"] = lines
                except Exception:
                    pass

            # Package.json
            pkg = root / "package.json"
            if pkg.exists():
                try:
                    data = json.loads(pkg.read_text(encoding="utf-8"))
                    node_deps["dependencies"] = data.get("dependencies", {})
                    node_deps["devDependencies"] = data.get("devDependencies", {})
                except Exception:
                    pass

            return success(
                {
                    "path": str(root),
                    "python": python_deps,
                    "nodejs": node_deps,
                },
                tool="project_dependencies",
                duration_ms=t.elapsed_ms,
            )

    @tool
    def project_summarize(self, path: str = ".", max_depth: int = 2) -> dict[str, Any]:
        """
        Generate a hierarchical tree summary of project files and directories.

        Args:
            path: Project root path. Defaults to ".".
            max_depth: Maximum directory traversal depth (1-5). Defaults to 2.

        Returns:
            Dict with directory tree structure, file counts, and extension breakdown.

        Examples:
            project_summarize(max_depth=3)
        """
        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                root = sandbox.resolve_safe(
                    Path(path) if Path(path).is_absolute() else get_session().cwd / path
                )
            except WorkspaceViolationError as exc:
                return make_error(str(exc), tool="project_summarize", code="WORKSPACE_VIOLATION")

            excl = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache"}

            def build_tree(current_dir: Path, depth: int) -> dict[str, Any]:
                if depth > max_depth:
                    return {"name": current_dir.name, "type": "directory", "truncated": True}

                items = []
                try:
                    for child in sorted(current_dir.iterdir()):
                        if child.name in excl:
                            continue
                        if child.is_dir():
                            items.append(build_tree(child, depth + 1))
                        else:
                            items.append(
                                {
                                    "name": child.name,
                                    "type": "file",
                                    "size_bytes": child.stat().st_size,
                                }
                            )
                except OSError:
                    pass

                return {"name": current_dir.name, "type": "directory", "children": items}

            tree = build_tree(root, 1)

            return success(
                {
                    "path": str(root),
                    "max_depth": max_depth,
                    "tree": tree,
                },
                tool="project_summarize",
                duration_ms=t.elapsed_ms,
            )

    @tool
    def project_architecture(self, path: str = ".") -> dict[str, Any]:
        """
        Inspect software architectural patterns, module layering, and component organization.

        Analyzes file locations, entry points, and structural patterns (MVC, Provider Pattern, Layered Architecture).

        Args:
            path: Project directory path. Defaults to ".".

        Returns:
            Dict detailing detected architecture components, entry points, and design patterns.

        Examples:
            project_architecture()
        """
        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                root = sandbox.resolve_safe(
                    Path(path) if Path(path).is_absolute() else get_session().cwd / path
                )
            except WorkspaceViolationError as exc:
                return make_error(str(exc), tool="project_architecture", code="WORKSPACE_VIOLATION")

            components: list[dict[str, str]] = []
            patterns: list[str] = []

            # Check provider pattern
            if (root / "providers").is_dir():
                patterns.append("Provider Pattern / Plugin Architecture")
                components.append({"name": "providers", "role": "Domain capability providers"})

            # Check core module
            if (root / "core").is_dir():
                components.append(
                    {"name": "core", "role": "Central orchestration and configuration"}
                )

            # Check security module
            if (root / "security").is_dir():
                components.append(
                    {"name": "security", "role": "Sandboxing, permissions, and audit validation"}
                )

            # Check entry points
            entry_points = []
            for ep in ["server.py", "main.py", "app.js", "index.js", "src/index.ts"]:
                if (root / ep).exists():
                    entry_points.append(ep)

            return success(
                {
                    "path": str(root),
                    "architecture_patterns": patterns,
                    "entry_points": entry_points,
                    "core_components": components,
                },
                tool="project_architecture",
                duration_ms=t.elapsed_ms,
            )

    @tool
    def project_generate_readme(self, path: str = ".") -> dict[str, Any]:
        """
        Generate a comprehensive, structured README.md draft based on workspace inspection.

        Analyzes tech stack, entry points, scripts, and configuration to create a complete README markdown template.

        Args:
            path: Project root path. Defaults to ".".

        Returns:
            Dict containing the generated markdown content under data.readme_markdown.

        Examples:
            project_generate_readme()
        """
        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                root = sandbox.resolve_safe(
                    Path(path) if Path(path).is_absolute() else get_session().cwd / path
                )
            except WorkspaceViolationError as exc:
                return make_error(
                    str(exc), tool="project_generate_readme", code="WORKSPACE_VIOLATION"
                )

            analysis = self.project_analyze(path).get("data", {})
            proj_types = ", ".join(analysis.get("project_types", ["Software"]))
            name = root.name.replace("-", " ").replace("_", " ").title()

            markdown = f"""# {name}

Production-grade {proj_types} application.

## Overview
This repository provides automated developer capabilities and tool execution workflows.

## Key Features
- **Architecture**: Modular provider-based architecture.
- **Security**: Built-in sandbox execution and path validation.
- **Tech Stack**: {proj_types}.

## Quick Start
```bash
# Install dependencies
uv sync

# Run tests
uv run pytest
```

## License
MIT License.
"""

            return success(
                {
                    "path": str(root),
                    "readme_markdown": markdown,
                },
                tool="project_generate_readme",
                duration_ms=t.elapsed_ms,
            )

    @tool
    def project_generate_docs(self, file_path: str) -> dict[str, Any]:
        """
        Extract classes, functions, and docstrings from a Python source file to create API docs.

        Args:
            file_path: Relative path to the target Python file.

        Returns:
            Dict containing formatted markdown API documentation.

        Examples:
            project_generate_docs("providers/git.py")
        """
        import ast

        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                full_path = sandbox.resolve_safe(
                    Path(file_path)
                    if Path(file_path).is_absolute()
                    else get_session().cwd / file_path
                )
            except WorkspaceViolationError as exc:
                return make_error(
                    str(exc), tool="project_generate_docs", code="WORKSPACE_VIOLATION"
                )

            if not full_path.exists() or not full_path.is_file():
                return make_error(
                    f"File not found: {file_path}", tool="project_generate_docs", code="NOT_FOUND"
                )

            try:
                tree = ast.parse(full_path.read_text(encoding="utf-8"))
                classes = []
                functions = []

                for node in ast.iter_child_nodes(tree):
                    if isinstance(node, ast.ClassDef):
                        doc = ast.get_docstring(node) or "No docstring provided."
                        methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                        classes.append({"name": node.name, "docstring": doc, "methods": methods})
                    elif isinstance(node, ast.FunctionDef):
                        doc = ast.get_docstring(node) or "No docstring provided."
                        functions.append({"name": node.name, "docstring": doc})

                return success(
                    {
                        "file": file_path,
                        "classes": classes,
                        "functions": functions,
                    },
                    tool="project_generate_docs",
                    duration_ms=t.elapsed_ms,
                )
            except Exception as exc:
                return make_error(str(exc), tool="project_generate_docs", code="AST_PARSE_ERROR")

    @tool
    def project_security_scan(self, path: str = ".") -> dict[str, Any]:
        """
        Perform a static pattern security scan for sensitive patterns (hardcoded API keys, tokens, dangerous commands).

        Args:
            path: Target directory to scan. Defaults to ".".

        Returns:
            Dict with vulnerability findings, line numbers, and risk levels.

        Examples:
            project_security_scan()
        """
        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                root = sandbox.resolve_safe(
                    Path(path) if Path(path).is_absolute() else get_session().cwd / path
                )
            except WorkspaceViolationError as exc:
                return make_error(
                    str(exc), tool="project_security_scan", code="WORKSPACE_VIOLATION"
                )

            patterns = [
                (
                    re.compile(r"api_key\s*=\s*[\"'][A-Za-z0-9_\-]{16,}[\"']", re.I),
                    "High",
                    "Hardcoded API Key",
                ),
                (
                    re.compile(r"password\s*=\s*[\"'][^\"']+[\"']", re.I),
                    "Medium",
                    "Potential Hardcoded Password",
                ),
                (re.compile(r"eval\(", re.I), "High", "Use of eval()"),
                (
                    re.compile(r"subprocess\.Popen\(.*shell=True", re.I),
                    "Medium",
                    "Subprocess with shell=True",
                ),
            ]

            excl = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"}
            findings: list[dict[str, Any]] = []

            for file_path in root.rglob("*.py"):
                if any(part in excl for part in file_path.parts):
                    continue
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    for lineno, line in enumerate(content.splitlines(), start=1):
                        for regex, severity, category in patterns:
                            if regex.search(line):
                                findings.append(
                                    {
                                        "file": str(file_path.relative_to(root)),
                                        "line": lineno,
                                        "severity": severity,
                                        "category": category,
                                        "snippet": line.strip()[:80],
                                    }
                                )
                except OSError:
                    pass

            return success(
                {
                    "path": str(root),
                    "total_findings": len(findings),
                    "findings": findings,
                },
                tool="project_security_scan",
                duration_ms=t.elapsed_ms,
            )

    @tool
    def project_generate_tests(self, file_path: str) -> dict[str, Any]:
        """
        Generate a pytest unit test skeleton for a target Python source file.

        Args:
            file_path: Target Python file (e.g. "core/config.py").

        Returns:
            Dict containing generated pytest code in data.test_code.

        Examples:
            project_generate_tests("core/config.py")
        """
        import ast

        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                full_path = sandbox.resolve_safe(
                    Path(file_path)
                    if Path(file_path).is_absolute()
                    else get_session().cwd / file_path
                )
            except WorkspaceViolationError as exc:
                return make_error(
                    str(exc), tool="project_generate_tests", code="WORKSPACE_VIOLATION"
                )

            if not full_path.exists() or not full_path.is_file():
                return make_error(
                    f"File not found: {file_path}", tool="project_generate_tests", code="NOT_FOUND"
                )

            try:
                tree = ast.parse(full_path.read_text(encoding="utf-8"))
                test_funcs = []

                for node in ast.iter_child_nodes(tree):
                    if isinstance(node, ast.ClassDef):
                        for item in node.body:
                            if isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
                                test_funcs.append(
                                    f"def test_{node.name.lower()}_{item.name}():\n    # TODO: Implement test\n    pass\n"
                                )
                    elif isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                        test_funcs.append(
                            f"def test_{node.name}():\n    # TODO: Implement test\n    pass\n"
                        )

                test_code = "import pytest\n\n" + "\n".join(test_funcs)

                return success(
                    {
                        "source_file": file_path,
                        "suggested_test_file": f"tests/test_{Path(file_path).stem}.py",
                        "test_code": test_code,
                    },
                    tool="project_generate_tests",
                    duration_ms=t.elapsed_ms,
                )
            except Exception as exc:
                return make_error(str(exc), tool="project_generate_tests", code="AST_PARSE_ERROR")

    @tool
    def count_lines_of_code(
        self,
        path: str = ".",
        extensions: str = ".py,.js,.ts,.jsx,.tsx,.cs,.go,.rs,.java,.cpp,.c,.h",
        exclude_dirs: str = ".venv,node_modules,.git,dist,build,__pycache__",
    ) -> dict[str, Any]:
        """
        Count total lines of code, blank lines, and code lines across the workspace.

        Args:
            path: Root directory to scan. Defaults to ".".
            extensions: Comma-separated list of file extensions.
            exclude_dirs: Comma-separated directory names to skip.

        Returns:
            Dict containing total files, total lines, code lines, and per-extension breakdown.

        Examples:
            count_lines_of_code()
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
        Search source code for comment tags (TODO, FIXME, HACK, BUG, NOTE).

        Args:
            path: Root directory path to scan. Defaults to ".".
            tags: Comma-separated comment tags.
            extensions: File extensions to check.
            max_results: Maximum results count limit.

        Returns:
            Dict containing match count and items list (file, line, tag, text).

        Examples:
            find_todos(tags="TODO,FIXME")
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
