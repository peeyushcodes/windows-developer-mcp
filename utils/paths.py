"""
Path utilities for Windows Developer MCP.

Provides safe path manipulation helpers used by the sandbox, filesystem
provider, and executor to resolve and validate file paths.

All public functions are pure (no side effects) and work with both ``str``
and ``pathlib.Path`` inputs.

Usage::

    from utils.paths import normalize_path, is_within, resolve_relative

    safe = resolve_relative("../config.toml", base=Path("/projects/myapp"))
    assert is_within(safe, root=Path("/projects"))
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath


def normalize_path(path: str | Path) -> Path:
    """
    Resolve and normalise a path to an absolute ``Path``.

    Expands ``~`` (home directory), environment variables, and resolves
    ``..`` components. The path does **not** need to exist.

    Args:
        path: A string or ``Path`` to normalise.

    Returns:
        An absolute, normalised ``Path``.
    """
    return Path(path).expanduser().resolve()


def is_within(path: Path, *, root: Path) -> bool:
    """
    Return ``True`` if ``path`` is contained within ``root``.

    Both inputs are normalised before comparison, so symlinks and ``..``
    components cannot escape the root.

    Args:
        path: The path to check.
        root: The required ancestor directory.

    Returns:
        ``True`` if ``path`` is ``root`` or a descendant of ``root``.
    """
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def resolve_relative(path: str | Path, *, base: Path) -> Path:
    """
    Resolve a possibly-relative path against a base directory.

    If ``path`` is already absolute, it is returned normalised.
    If it is relative, it is joined to ``base`` and then normalised.

    Args:
        path: The path to resolve.
        base: The base directory for relative resolution.

    Returns:
        A normalised absolute ``Path``.
    """
    p = Path(path)
    if p.is_absolute():
        return p.resolve()
    return (base / p).resolve()


def safe_relative(path: Path, *, root: Path) -> Path:
    """
    Return ``path`` relative to ``root``, without raising.

    If ``path`` is not under ``root``, returns ``path`` unchanged.

    Args:
        path: The absolute path to make relative.
        root: The root directory.

    Returns:
        A relative ``Path`` if possible, otherwise ``path`` unchanged.
    """
    try:
        return path.resolve().relative_to(root.resolve())
    except ValueError:
        return path


def ensure_directory(path: Path) -> Path:
    """
    Create ``path`` and all parent directories if they do not exist.

    Args:
        path: The directory to create.

    Returns:
        The (now-existing) directory ``Path``.

    Raises:
        NotADirectoryError: If ``path`` exists but is a file.
    """
    if path.exists() and not path.is_dir():
        raise NotADirectoryError(f"Path exists but is not a directory: {path}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def windows_path(path: Path) -> str:
    """
    Return a Windows-style path string (backslashes).

    Useful when building command strings for PowerShell or CMD.

    Args:
        path: The path to convert.

    Returns:
        A string with Windows-style separators.
    """
    return str(PureWindowsPath(path))


def posix_path(path: Path) -> str:
    """
    Return a POSIX-style path string (forward slashes).

    Useful when building command strings for Git and other POSIX-aware tools.

    Args:
        path: The path to convert.

    Returns:
        A string with POSIX-style separators.
    """
    return str(PurePosixPath(path))


def has_extension(path: Path, *extensions: str) -> bool:
    """
    Return ``True`` if ``path`` has one of the given extensions.

    Extension comparison is case-insensitive. Extensions should be supplied
    with a leading dot (e.g. ``".py"``, ``".toml"``).

    Args:
        path:       The path to check.
        extensions: One or more extensions to test against.

    Returns:
        ``True`` if the path suffix matches any of the given extensions.
    """
    suffix = path.suffix.lower()
    return suffix in {ext.lower() for ext in extensions}


def find_upward(start: Path, filename: str) -> Path | None:
    """
    Walk upward from ``start`` to find the nearest ``filename``.

    Useful for locating project roots (``pyproject.toml``, ``package.json``,
    ``.git``, etc.) from a nested working directory.

    Args:
        start:    Directory to begin the search from.
        filename: File or directory name to look for.

    Returns:
        The ``Path`` of the first match found, or ``None``.
    """
    current = start.resolve()
    while True:
        candidate = current / filename
        if candidate.exists():
            return candidate
        parent = current.parent
        if parent == current:
            return None
        current = parent
