"""
Per-request context for Windows Developer MCP.

A ``RequestContext`` is created for each MCP tool invocation and carries
metadata (tool name, request ID, timestamp) through the entire execution
pipeline: validator → permission manager → logger → executor → result.

This eliminates the need to thread tool-name and request-ID parameters
through every function signature.

Usage::

    ctx = RequestContext(tool_name="git_status")
    executor.run(command, context=ctx)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import uuid


@dataclass
class RequestContext:
    """
    Immutable metadata attached to a single MCP tool invocation.

    Attributes:
        tool_name:  The name of the MCP tool being invoked.
        request_id: A unique UUID for this request, auto-generated if not provided.
        timestamp:  UTC datetime when the context was created.
        caller:     Optional identifier for the upstream client.
    """

    tool_name: str
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    caller: str = ""

    @property
    def elapsed_ms(self) -> int:
        """Return milliseconds elapsed since this context was created."""
        delta = datetime.now(UTC) - self.timestamp
        return int(delta.total_seconds() * 1000)

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-serialisable representation of the context."""
        return {
            "tool_name": self.tool_name,
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
            "caller": self.caller,
        }

    def __repr__(self) -> str:
        return f"RequestContext(tool={self.tool_name!r}, request_id={self.request_id[:8]!r}…)"
