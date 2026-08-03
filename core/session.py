"""
Persistent session state for Windows Developer MCP.

A ``Session`` object survives across multiple MCP tool calls within a single
server process. It tracks the current working directory, command history,
active virtual environment, active Git repository, and environment variable
overrides.

The session is a module-level singleton (``get_session()``). All mutations
are protected by a threading lock so concurrent tool calls do not corrupt state.

Usage::

    from core.session import get_session

    session = get_session()
    session.change_directory("/projects/myapp")
    print(session.cwd)          # PosixPath('/projects/myapp')
    print(session.cwd_str)      # '/projects/myapp'
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
import threading

# ==============================================================================
# History Entry
# ==============================================================================


@dataclass
class HistoryEntry:
    """
    A single recorded command in the session history.

    Attributes:
        command:     The raw command string.
        tool:        The MCP tool that executed the command.
        exit_code:   The process exit code (0 = success).
        timestamp:   UTC datetime of execution.
        duration_ms: Execution time in milliseconds.
    """

    command: str
    tool: str = ""
    exit_code: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    duration_ms: int = 0

    def to_dict(self) -> dict[str, str | int]:
        """Return a JSON-serialisable representation."""
        return {
            "command": self.command,
            "tool": self.tool,
            "exit_code": self.exit_code,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
        }


# ==============================================================================
# Session
# ==============================================================================


class Session:
    """
    Thread-safe persistent session state across MCP tool calls.

    The session tracks:
    - Current working directory (``cwd``)
    - Command history with metadata
    - Active Python virtual environment path
    - Active Git repository root
    - Active project path
    - Per-session environment variable overrides
    - Last command and exit code
    - Session start time

    All public mutating methods acquire the internal lock before modifying
    state, making this class safe for concurrent use.
    """

    MAX_HISTORY: int = 500

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cwd: Path = Path.home()
        self._history: list[HistoryEntry] = []
        self._env: dict[str, str] = {}
        self._active_venv: Path | None = None
        self._active_git_repo: Path | None = None
        self._active_project: Path | None = None
        self._last_exit_code: int = 0
        self._started_at: datetime = datetime.now(UTC)

    # ------------------------------------------------------------------
    # Working Directory
    # ------------------------------------------------------------------

    @property
    def cwd(self) -> Path:
        """Current working directory as a ``Path`` object."""
        with self._lock:
            return self._cwd

    @property
    def cwd_str(self) -> str:
        """Current working directory as a POSIX-style string."""
        with self._lock:
            return str(self._cwd)

    def change_directory(self, path: str) -> Path:
        """
        Change the current working directory.

        Resolves relative paths against the current ``cwd``. Does NOT
        enforce workspace restrictions — that is the sandbox's responsibility.

        Args:
            path: Absolute or relative target directory path.

        Returns:
            The new resolved ``Path``.

        Raises:
            FileNotFoundError: If the target path does not exist.
            NotADirectoryError: If the target path is not a directory.
        """
        target = Path(path)
        with self._lock:
            if not target.is_absolute():
                target = (self._cwd / target).resolve()
            else:
                target = target.resolve()

        if not target.exists():
            raise FileNotFoundError(f"Directory not found: {target}")
        if not target.is_dir():
            raise NotADirectoryError(f"Not a directory: {target}")

        with self._lock:
            self._cwd = target
            # Update active git repo if we moved inside one
            self._active_git_repo = self._detect_git_root(target)
        return target

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def add_history(
        self,
        command: str,
        *,
        tool: str = "",
        exit_code: int = 0,
        duration_ms: int = 0,
    ) -> None:
        """
        Append a command to the session history.

        Trims the history to ``MAX_HISTORY`` entries (dropping the oldest)
        to prevent unbounded memory growth.

        Args:
            command:     The executed command string.
            tool:        The MCP tool name that triggered the command.
            exit_code:   The process exit code.
            duration_ms: Execution duration in milliseconds.
        """
        entry = HistoryEntry(
            command=command,
            tool=tool,
            exit_code=exit_code,
            duration_ms=duration_ms,
        )
        with self._lock:
            self._history.append(entry)
            if len(self._history) > self.MAX_HISTORY:
                self._history = self._history[-self.MAX_HISTORY :]
            self._last_exit_code = exit_code

    def get_history(self, limit: int = 50) -> list[dict[str, str | int]]:
        """
        Return the most recent ``limit`` history entries.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            A list of serialised :class:`HistoryEntry` dicts, newest last.
        """
        with self._lock:
            entries = self._history[-limit:]
        return [e.to_dict() for e in entries]

    def clear_history(self) -> None:
        """Erase all session history."""
        with self._lock:
            self._history.clear()

    # ------------------------------------------------------------------
    # Exit Code
    # ------------------------------------------------------------------

    @property
    def last_exit_code(self) -> int:
        """Exit code of the most recently completed command."""
        with self._lock:
            return self._last_exit_code

    def set_exit_code(self, code: int) -> None:
        """Record the exit code of the last command."""
        with self._lock:
            self._last_exit_code = code

    # ------------------------------------------------------------------
    # Environment Variables
    # ------------------------------------------------------------------

    def set_env(self, key: str, value: str) -> None:
        """
        Set a session-scoped environment variable override.

        These overrides are passed to every subprocess spawned by the executor
        on top of the inherited process environment.

        Args:
            key:   The environment variable name.
            value: The value to set.
        """
        with self._lock:
            self._env[key] = value

    def get_env(self, key: str) -> str | None:
        """Return the session-scoped value for ``key``, or ``None`` if unset."""
        with self._lock:
            return self._env.get(key)

    def get_all_env(self) -> dict[str, str]:
        """Return a snapshot of all session-scoped environment variable overrides."""
        with self._lock:
            return dict(self._env)

    def unset_env(self, key: str) -> None:
        """Remove a session-scoped environment variable override."""
        with self._lock:
            self._env.pop(key, None)

    # ------------------------------------------------------------------
    # Active Context (venv / git repo / project)
    # ------------------------------------------------------------------

    @property
    def active_venv(self) -> Path | None:
        """Path to the active Python virtual environment, or ``None``."""
        with self._lock:
            return self._active_venv

    def set_active_venv(self, path: Path | None) -> None:
        """Set or clear the active virtual environment path."""
        with self._lock:
            self._active_venv = path

    @property
    def active_git_repo(self) -> Path | None:
        """Root path of the active Git repository, or ``None``."""
        with self._lock:
            return self._active_git_repo

    def set_active_git_repo(self, path: Path | None) -> None:
        """Manually override the active Git repository root."""
        with self._lock:
            self._active_git_repo = path

    @property
    def active_project(self) -> Path | None:
        """Root path of the active project, or ``None``."""
        with self._lock:
            return self._active_project

    def set_active_project(self, path: Path | None) -> None:
        """Set the active project root."""
        with self._lock:
            self._active_project = path

    # ------------------------------------------------------------------
    # Session Metadata
    # ------------------------------------------------------------------

    @property
    def started_at(self) -> datetime:
        """UTC datetime when this session was created."""
        return self._started_at

    def to_dict(self) -> dict[str, object]:
        """Return a full JSON-serialisable snapshot of the session state."""
        with self._lock:
            return {
                "cwd": str(self._cwd),
                "last_exit_code": self._last_exit_code,
                "history_count": len(self._history),
                "active_venv": str(self._active_venv) if self._active_venv else None,
                "active_git_repo": (str(self._active_git_repo) if self._active_git_repo else None),
                "active_project": (str(self._active_project) if self._active_project else None),
                "env_overrides": list(self._env.keys()),
                "started_at": self._started_at.isoformat(),
            }

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_git_root(path: Path) -> Path | None:
        """
        Walk upwards from ``path`` to find a ``.git`` directory.

        Args:
            path: Starting directory.

        Returns:
            The repository root ``Path``, or ``None`` if not in a repo.
        """
        current = path
        while True:
            if (current / ".git").exists():
                return current
            parent = current.parent
            if parent == current:
                return None
            current = parent


# ==============================================================================
# Module-Level Singleton
# ==============================================================================

_session: Session | None = None


def get_session() -> Session:
    """
    Return the global session singleton.

    The session is created lazily on first access and persists for the
    lifetime of the server process.

    Returns:
        The application :class:`Session` instance.
    """
    global _session
    if _session is None:
        _session = Session()
    return _session


def reset_session() -> None:
    """
    Replace the session singleton with a fresh instance.

    Intended for use in tests only.
    """
    global _session
    _session = Session()
