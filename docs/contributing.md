# Contributing Guide — Windows Developer MCP Server

Thank you for contributing to **Windows Developer MCP**!

---

## Development Setup

1. **Prerequisites**:
   - Python 3.12+
   - `uv` package manager (`pip install uv` or `winget install astral-sh.uv`)

2. **Clone and Install Dependencies**:
   ```bash
   git clone https://github.com/peeyushcodes/windows-developer-mcp.git
   cd windows-developer-mcp
   uv sync --all-extras --dev
   ```

3. **Install Pre-Commit Hooks**:
   ```bash
   uv run pre-commit install
   ```

---

## Code Quality Standards

We enforce strict linting, formatting, and type-checking rules:

1. **Linter & Formatter (`ruff`)**:
   ```bash
   uv run ruff check .
   uv run ruff format .
   ```

2. **Type Checker (`basedpyright`)**:
   ```bash
   uv run basedpyright
   ```

3. **Test Suite (`pytest`)**:
   ```bash
   uv run pytest
   ```

---

## Adding a New Provider

1. Create a file under `providers/<name>.py`.
2. Inherit from `BaseProvider` (`from providers.base import BaseProvider, tool`).
3. Set `name` and `description` attributes.
4. Decorate tool methods with `@tool` and provide Google/Sphinx style docstrings with typed parameters and return specifications.
5. Add registration line in `server.py`.
6. Add unit tests under `tests/test_providers/test_<name>_provider.py`.
