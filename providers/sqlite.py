"""
SQLite provider for Windows Developer MCP.

Provides safe SQLite database inspection and querying tools.
Write queries require explicit confirmation.

Tools:
    sqlite_list_tables   — List all tables in a database
    sqlite_schema        — Show CREATE statements for tables
    sqlite_execute       — Execute a SQL query
    sqlite_table_info    — Column definitions for a table
    sqlite_query         — Execute a read-only SELECT query
    sqlite_databases     — Search for .db files in the workspace
"""

from __future__ import annotations

import logging
from pathlib import Path
import sqlite3
from typing import Any

from core.exceptions import WorkspaceViolationError
from core.session import get_session
from providers.base import BaseProvider, tool
from security.sandbox import WorkspaceSandbox
from utils.helpers import Timer
from utils.json_utils import (
    confirmation_required,
    not_found,
    success,
)
from utils.json_utils import (
    error as make_error,
)

logger = logging.getLogger(__name__)

_WRITE_KEYWORDS = frozenset(
    {"INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE", "REPLACE"}
)


def _is_write_query(sql: str) -> bool:
    """Return True if the query appears to be a write operation."""
    first_word = sql.strip().split()[0].upper() if sql.strip() else ""
    return first_word in _WRITE_KEYWORDS


def _resolve_db(path: str, sandbox: WorkspaceSandbox) -> Path:
    """Resolve a database path within the workspace."""
    session = get_session()
    raw = Path(path) if Path(path).is_absolute() else session.cwd / path
    return sandbox.resolve_safe(raw)


class SQLiteProvider(BaseProvider):
    """
    Provides SQLite database inspection and query execution.

    Write operations (INSERT, UPDATE, DELETE, CREATE, etc.) require
    explicit confirmation via ``confirm=True``.
    """

    name = "sqlite"
    description = "SQLite query execution, table listing, schema inspection."

    @tool
    def sqlite_list_tables(self, database: str) -> dict[str, Any]:
        """
        List all tables in a SQLite database file.

        Args:
            database: Path to the .db or .sqlite file.

        Returns:
            A dict with keys: status, data (tables list, count).

        Examples:
            sqlite_list_tables("app.db")
            sqlite_list_tables("C:/data/mydb.sqlite")
        """
        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                db_path = _resolve_db(database, sandbox)
            except WorkspaceViolationError as exc:
                return make_error(str(exc), tool="sqlite_list_tables", code="WORKSPACE_VIOLATION")

            if not db_path.exists():
                return not_found(f"Database {db_path}", tool="sqlite_list_tables")

            try:
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.execute(
                        "SELECT name, type FROM sqlite_master WHERE type IN ('table','view') ORDER BY name"
                    )
                    rows = cursor.fetchall()
                return success(
                    {
                        "database": str(db_path),
                        "count": len(rows),
                        "tables": [{"name": r[0], "type": r[1]} for r in rows],
                    },
                    tool="sqlite_list_tables",
                    duration_ms=t.elapsed_ms,
                )
            except sqlite3.Error as exc:
                return make_error(str(exc), tool="sqlite_list_tables", code="SQLITE_ERROR")

    @tool
    def sqlite_schema(self, database: str, table: str = "") -> dict[str, Any]:
        """
        Return the CREATE statement(s) for tables in a database.

        Args:
            database: Path to the database file.
            table:    Specific table name. Leave empty to show all tables.

        Returns:
            A dict with keys: status, data (schema strings).

        Examples:
            sqlite_schema("app.db")
            sqlite_schema("app.db", table="users")
        """
        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                db_path = _resolve_db(database, sandbox)
            except WorkspaceViolationError as exc:
                return make_error(str(exc), tool="sqlite_schema", code="WORKSPACE_VIOLATION")

            if not db_path.exists():
                return not_found(f"Database {db_path}", tool="sqlite_schema")

            try:
                with sqlite3.connect(db_path) as conn:
                    if table:
                        cursor = conn.execute(
                            "SELECT sql FROM sqlite_master WHERE name = ? AND sql IS NOT NULL",
                            (table,),
                        )
                    else:
                        cursor = conn.execute(
                            "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type, name"
                        )
                    rows = cursor.fetchall()
                schemas = [r[0] for r in rows if r[0]]
                return success(
                    {
                        "database": str(db_path),
                        "table": table or "all",
                        "schemas": schemas,
                        "schema_text": "\n\n".join(schemas),
                    },
                    tool="sqlite_schema",
                    duration_ms=t.elapsed_ms,
                )
            except sqlite3.Error as exc:
                return make_error(str(exc), tool="sqlite_schema", code="SQLITE_ERROR")

    @tool
    def sqlite_table_info(self, database: str, table: str) -> dict[str, Any]:
        """
        Return column definitions for a specific table.

        Args:
            database: Path to the database file.
            table:    The table name to inspect.

        Returns:
            A dict with keys: status, data (columns list with name/type/nullable/default).

        Examples:
            sqlite_table_info("app.db", "users")
        """
        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                db_path = _resolve_db(database, sandbox)
            except WorkspaceViolationError as exc:
                return make_error(str(exc), tool="sqlite_table_info", code="WORKSPACE_VIOLATION")

            if not db_path.exists():
                return not_found(f"Database {db_path}", tool="sqlite_table_info")

            try:
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.execute(f"PRAGMA table_info({table!r})")
                    rows = cursor.fetchall()
                if not rows:
                    return not_found(f"Table {table!r} in {db_path}", tool="sqlite_table_info")
                columns = [
                    {
                        "cid": r[0],
                        "name": r[1],
                        "type": r[2],
                        "not_null": bool(r[3]),
                        "default": r[4],
                        "primary_key": bool(r[5]),
                    }
                    for r in rows
                ]
                return success(
                    {
                        "database": str(db_path),
                        "table": table,
                        "column_count": len(columns),
                        "columns": columns,
                    },
                    tool="sqlite_table_info",
                    duration_ms=t.elapsed_ms,
                )
            except sqlite3.Error as exc:
                return make_error(str(exc), tool="sqlite_table_info", code="SQLITE_ERROR")

    @tool
    def sqlite_query(
        self,
        database: str,
        sql: str,
        params: list[Any] | None = None,
        max_rows: int = 500,
    ) -> dict[str, Any]:
        """
        Execute a read-only SELECT query against a SQLite database.

        Only SELECT statements are allowed. Use sqlite_execute for writes.

        Args:
            database: Path to the database file.
            sql:      The SELECT query to execute.
            params:   Optional query parameters (for parameterised queries).
            max_rows: Maximum rows to return (1–5000). Default: 500.

        Returns:
            A dict with keys: status, data (columns, rows, count, truncated).

        Examples:
            sqlite_query("app.db", "SELECT * FROM users LIMIT 10")
            sqlite_query("app.db", "SELECT count(*) FROM orders WHERE status = ?", params=["pending"])
        """
        if not sql.strip().upper().startswith("SELECT"):
            return make_error(
                "sqlite_query only allows SELECT statements. Use sqlite_execute for writes.",
                tool="sqlite_query",
                code="NOT_ALLOWED",
            )

        sandbox = WorkspaceSandbox()
        max_rows = max(1, min(max_rows, 5000))

        with Timer() as t:
            try:
                db_path = _resolve_db(database, sandbox)
            except WorkspaceViolationError as exc:
                return make_error(str(exc), tool="sqlite_query", code="WORKSPACE_VIOLATION")

            if not db_path.exists():
                return not_found(f"Database {db_path}", tool="sqlite_query")

            try:
                with sqlite3.connect(db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.execute(sql, params or [])
                    all_rows = cursor.fetchmany(max_rows + 1)
                    truncated = len(all_rows) > max_rows
                    rows = all_rows[:max_rows]
                    columns = [desc[0] for desc in cursor.description] if cursor.description else []
                    data_rows = [dict(zip(columns, row, strict=False)) for row in rows]

                return success(
                    {
                        "database": str(db_path),
                        "sql": sql,
                        "columns": columns,
                        "count": len(data_rows),
                        "truncated": truncated,
                        "rows": data_rows,
                    },
                    tool="sqlite_query",
                    duration_ms=t.elapsed_ms,
                )
            except sqlite3.Error as exc:
                return make_error(str(exc), tool="sqlite_query", code="SQLITE_ERROR")

    @tool
    def sqlite_execute(
        self,
        database: str,
        sql: str,
        params: list[Any] | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        """
        Execute any SQL statement against a SQLite database.

        Write operations (INSERT, UPDATE, DELETE, CREATE, DROP, etc.) require
        explicit confirmation.

        Args:
            database: Path to the database file.
            sql:      The SQL statement to execute.
            params:   Optional query parameters.
            confirm:  Set to True to confirm write operations.

        Returns:
            A dict with keys: status, data (rows_affected, lastrowid for writes;
            columns/rows/count for SELECTs).

        Examples:
            sqlite_execute("app.db", "SELECT * FROM users")
            sqlite_execute("app.db", "INSERT INTO users (name) VALUES (?)", params=["Alice"], confirm=True)
        """
        from core.exceptions import ConfirmationRequiredError
        from security.permissions import PermissionManager

        is_write = _is_write_query(sql)
        if is_write:
            pm = PermissionManager()
            if pm.requires_confirmation("sqlite_execute"):
                try:
                    pm.assert_confirmed(action=f"sqlite write: {sql[:60]}", confirm=confirm)
                except ConfirmationRequiredError:
                    return confirmation_required(
                        f"SQLite write: {sql[:60]}", tool="sqlite_execute"
                    )

        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                db_path = _resolve_db(database, sandbox)
            except WorkspaceViolationError as exc:
                return make_error(str(exc), tool="sqlite_execute", code="WORKSPACE_VIOLATION")

            if not db_path.exists() and not is_write:
                return not_found(f"Database {db_path}", tool="sqlite_execute")

            try:
                with sqlite3.connect(db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.execute(sql, params or [])
                    if cursor.description:
                        # SELECT-like
                        rows = cursor.fetchall()
                        columns = [d[0] for d in cursor.description]
                        data_rows = [dict(zip(columns, row, strict=False)) for row in rows]
                        return success(
                            {
                                "database": str(db_path),
                                "sql": sql,
                                "columns": columns,
                                "count": len(data_rows),
                                "rows": data_rows,
                            },
                            tool="sqlite_execute",
                            duration_ms=t.elapsed_ms,
                        )
                    conn.commit()
                    return success(
                        {
                            "database": str(db_path),
                            "sql": sql,
                            "rows_affected": cursor.rowcount,
                            "lastrowid": cursor.lastrowid,
                        },
                        tool="sqlite_execute",
                        duration_ms=t.elapsed_ms,
                    )
            except sqlite3.Error as exc:
                return make_error(str(exc), tool="sqlite_execute", code="SQLITE_ERROR")

    @tool
    def sqlite_databases(self, search_path: str = ".") -> dict[str, Any]:
        """
        Search for SQLite database files within the workspace.

        Args:
            search_path: Directory to search. Defaults to the current working directory.

        Returns:
            A dict with keys: status, data (count, databases list with path/size).

        Examples:
            sqlite_databases()
            sqlite_databases("C:/projects")
        """
        sandbox = WorkspaceSandbox()
        with Timer() as t:
            try:
                root = sandbox.resolve_safe(
                    Path(search_path)
                    if Path(search_path).is_absolute()
                    else get_session().cwd / search_path
                )
            except WorkspaceViolationError as exc:
                return make_error(str(exc), tool="sqlite_databases", code="WORKSPACE_VIOLATION")

            found = []
            for ext in ("*.db", "*.sqlite", "*.sqlite3"):
                for db_file in root.rglob(ext):
                    stat = db_file.stat()
                    found.append(
                        {
                            "path": str(db_file),
                            "name": db_file.name,
                            "size_bytes": stat.st_size,
                        }
                    )

            return success(
                {"count": len(found), "databases": found},
                tool="sqlite_databases",
                duration_ms=t.elapsed_ms,
            )
