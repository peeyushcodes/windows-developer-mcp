"""
Structured dangerous command definitions for Windows Developer MCP.

Each entry in :data:`DANGEROUS_PATTERNS` is a :class:`DangerousPattern`
that maps a regex pattern to a category, severity, and description.
The :class:`CommandValidator` in ``security/validator.py`` uses this list
to reject commands before they reach the executor.

Design principles:
- Use regex patterns (``re.search``) instead of substring matching.
  Substring matching is bypassable with casing or whitespace tricks.
- Group patterns into semantic :class:`Category` groups so callers can
  understand *why* a command was blocked, not just *that* it was blocked.
- ``Severity.CRITICAL`` patterns are always blocked and cannot be
  overridden by an allowlist.
- New patterns should be added here, never inline in other modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re

# ==============================================================================
# Enums
# ==============================================================================


class Category(StrEnum):
    """Semantic grouping for dangerous commands."""

    DESTRUCTIVE = "destructive"           # Permanently destroys data or system state
    SYSTEM_MODIFY = "system_modify"       # Modifies OS-level configuration
    PRIVILEGE_ESCALATION = "priv_esc"     # Attempts to gain elevated privileges
    NETWORK_ATTACK = "network_attack"     # Could be used for network-based attacks
    REGISTRY_MODIFY = "registry_modify"  # Modifies the Windows registry
    PROCESS_CONTROL = "process_control"  # Kills or manipulates other processes
    CREDENTIAL_ACCESS = "cred_access"    # Access or modifies credentials/accounts


class Severity(StrEnum):
    """
    Risk severity for a matched dangerous command.

    - CRITICAL: Never allowed regardless of any configuration.
    - HIGH:     Blocked by default; cannot be allowlisted.
    - MEDIUM:   Blocked by default; may be enabled via config in the future.
    - LOW:      Warning only; not blocked by default (reserved for future use).
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ==============================================================================
# Pattern Definition
# ==============================================================================


@dataclass(frozen=True)
class DangerousPattern:
    """
    A single dangerous command definition.

    Attributes:
        name:        Unique machine-readable identifier for this pattern.
        pattern:     A regex pattern tested with ``re.search(..., re.IGNORECASE)``.
        category:    Semantic grouping.
        severity:    Risk severity level.
        description: Human-readable explanation of why this is dangerous.
    """

    name: str
    pattern: str
    category: Category
    severity: Severity
    description: str

    def matches(self, command: str) -> bool:
        """
        Return ``True`` if this pattern matches ``command``.

        Args:
            command: The command string to test (case-insensitive).

        Returns:
            ``True`` if the pattern is found anywhere within ``command``.
        """
        return bool(re.search(self.pattern, command, re.IGNORECASE))


# ==============================================================================
# Pattern Registry
# ==============================================================================

DANGEROUS_PATTERNS: tuple[DangerousPattern, ...] = (
    # -----------------------------------------------------------------------
    # DESTRUCTIVE — Data destruction
    # -----------------------------------------------------------------------
    DangerousPattern(
        name="format_disk",
        pattern=r"\bformat\s+[a-zA-Z]:",
        category=Category.DESTRUCTIVE,
        severity=Severity.CRITICAL,
        description="Formats a disk partition, erasing all data.",
    ),
    DangerousPattern(
        name="diskpart",
        pattern=r"\bdiskpart\b",
        category=Category.DESTRUCTIVE,
        severity=Severity.CRITICAL,
        description="Interactive disk partitioning tool — can wipe disks.",
    ),
    DangerousPattern(
        name="remove_item_force_recurse",
        pattern=r"\bremove-item\b.+(-recurse|-force)",
        category=Category.DESTRUCTIVE,
        severity=Severity.HIGH,
        description="Recursively and forcibly deletes files or directories.",
    ),
    DangerousPattern(
        name="rd_sys",
        pattern=r"\brd\b.+/s.+/q",
        category=Category.DESTRUCTIVE,
        severity=Severity.HIGH,
        description="Silently removes a directory tree (rd /s /q).",
    ),
    DangerousPattern(
        name="rmdir_sys",
        pattern=r"\brmdir\b.+/s",
        category=Category.DESTRUCTIVE,
        severity=Severity.HIGH,
        description="Recursively removes a directory tree.",
    ),
    DangerousPattern(
        name="mass_delete",
        pattern=r"\bdel\b.+/s",
        category=Category.DESTRUCTIVE,
        severity=Severity.CRITICAL,
        description="Recursively deletes files across directories (del /s).",
    ),
    DangerousPattern(
        name="del_force",
        pattern=r"\bdel\b.+/f",
        category=Category.DESTRUCTIVE,
        severity=Severity.HIGH,
        description="Force-deletes read-only files.",
    ),
    DangerousPattern(
        name="erase_force",
        pattern=r"\berase\b.+/f",
        category=Category.DESTRUCTIVE,
        severity=Severity.HIGH,
        description="Force-erases read-only files.",
    ),
    DangerousPattern(
        name="cipher_wipe",
        pattern=r"\bcipher\b.+/w",
        category=Category.DESTRUCTIVE,
        severity=Severity.HIGH,
        description="Wipes free space (cipher /w) — cannot be undone.",
    ),

    # -----------------------------------------------------------------------
    # SYSTEM_MODIFY — OS-level configuration changes
    # -----------------------------------------------------------------------
    DangerousPattern(
        name="shutdown",
        pattern=r"\bshutdown\b",
        category=Category.SYSTEM_MODIFY,
        severity=Severity.CRITICAL,
        description="Shuts down or reboots the computer.",
    ),
    DangerousPattern(
        name="restart_computer",
        pattern=r"\brestart-computer\b",
        category=Category.SYSTEM_MODIFY,
        severity=Severity.CRITICAL,
        description="Reboots the computer immediately.",
    ),
    DangerousPattern(
        name="stop_computer",
        pattern=r"\bstop-computer\b",
        category=Category.SYSTEM_MODIFY,
        severity=Severity.CRITICAL,
        description="Powers off the computer immediately.",
    ),
    DangerousPattern(
        name="bcdedit",
        pattern=r"\bbcdedit\b",
        category=Category.SYSTEM_MODIFY,
        severity=Severity.CRITICAL,
        description="Modifies the Windows Boot Configuration Data store.",
    ),
    DangerousPattern(
        name="sfc_purge",
        pattern=r"\bsfc\b.+/purge",
        category=Category.SYSTEM_MODIFY,
        severity=Severity.HIGH,
        description="Purges the Windows component store.",
    ),
    DangerousPattern(
        name="dism_remove",
        pattern=r"\bdism\b.+/remove",
        category=Category.SYSTEM_MODIFY,
        severity=Severity.HIGH,
        description="Removes Windows components.",
    ),
    DangerousPattern(
        name="encoded_powershell",
        pattern=r"\bpowershell\b.+-e(nc|ncodedcommand)?\b",
        category=Category.SYSTEM_MODIFY,
        severity=Severity.HIGH,
        description="Executes base64 encoded PowerShell commands.",
    ),
    DangerousPattern(
        name="execution_policy",
        pattern=r"\bset-executionpolicy\b.+(bypass|unrestricted)",
        category=Category.SYSTEM_MODIFY,
        severity=Severity.HIGH,
        description="Bypasses PowerShell script execution policy.",
    ),
    DangerousPattern(
        name="invoke_expression",
        pattern=r"\b(invoke-expression|iex)\b",
        category=Category.SYSTEM_MODIFY,
        severity=Severity.HIGH,
        description="Executes dynamic PowerShell expressions (Invoke-Expression / iex).",
    ),

    # -----------------------------------------------------------------------
    # REGISTRY_MODIFY — Windows registry manipulation
    # -----------------------------------------------------------------------
    DangerousPattern(
        name="reg_delete",
        pattern=r"\breg\s+delete\b",
        category=Category.REGISTRY_MODIFY,
        severity=Severity.HIGH,
        description="Deletes a registry key or value.",
    ),
    DangerousPattern(
        name="reg_add",
        pattern=r"\breg\s+add\b",
        category=Category.REGISTRY_MODIFY,
        severity=Severity.MEDIUM,
        description="Adds or modifies a registry key or value.",
    ),
    DangerousPattern(
        name="remove_itemproperty_hklm",
        pattern=r"\bremove-itemproperty\b.+hklm",
        category=Category.REGISTRY_MODIFY,
        severity=Severity.HIGH,
        description="Deletes a value from the HKLM registry hive.",
    ),

    # -----------------------------------------------------------------------
    # PRIVILEGE_ESCALATION — Gaining elevated access
    # -----------------------------------------------------------------------
    DangerousPattern(
        name="takeown",
        pattern=r"\btakeown\b",
        category=Category.PRIVILEGE_ESCALATION,
        severity=Severity.HIGH,
        description="Takes ownership of files or directories.",
    ),
    DangerousPattern(
        name="icacls_grant",
        pattern=r"\bicacls\b.+/grant",
        category=Category.PRIVILEGE_ESCALATION,
        severity=Severity.HIGH,
        description="Grants permissions to files or directories.",
    ),
    DangerousPattern(
        name="net_localgroup_admin",
        pattern=r"\bnet\s+localgroup\s+administrators\b",
        category=Category.PRIVILEGE_ESCALATION,
        severity=Severity.CRITICAL,
        description="Modifies the local Administrators group membership.",
    ),
    DangerousPattern(
        name="set_acl_admin",
        pattern=r"\bset-acl\b",
        category=Category.PRIVILEGE_ESCALATION,
        severity=Severity.HIGH,
        description="Modifies access control lists (ACLs).",
    ),

    # -----------------------------------------------------------------------
    # CREDENTIAL_ACCESS — Account and credential manipulation
    # -----------------------------------------------------------------------
    DangerousPattern(
        name="net_user",
        pattern=r"\bnet\s+user\b",
        category=Category.CREDENTIAL_ACCESS,
        severity=Severity.HIGH,
        description="Creates, modifies, or deletes user accounts.",
    ),
    DangerousPattern(
        name="net_user_password",
        pattern=r"\bnet\s+user\b.+\*",
        category=Category.CREDENTIAL_ACCESS,
        severity=Severity.CRITICAL,
        description="Changes a user account password.",
    ),

    # -----------------------------------------------------------------------
    # PROCESS_CONTROL — Terminating other processes
    # -----------------------------------------------------------------------
    DangerousPattern(
        name="taskkill_force",
        pattern=r"\btaskkill\b.+/f",
        category=Category.PROCESS_CONTROL,
        severity=Severity.MEDIUM,
        description="Forcibly terminates a running process.",
    ),
    DangerousPattern(
        name="wmic_process_delete",
        pattern=r"\bwmic\b.+process.+delete\b",
        category=Category.PROCESS_CONTROL,
        severity=Severity.HIGH,
        description="Terminates a process via WMI.",
    ),
    DangerousPattern(
        name="stop_service",
        pattern=r"\bstop-service\b.+(windefend|mpssvc|eventlog|lanmanserver)",
        category=Category.PROCESS_CONTROL,
        severity=Severity.HIGH,
        description="Stops a critical Windows system service.",
    ),
)

# Pre-compiled: critical and high severity patterns that are never overridable.
_NON_OVERRIDABLE_SEVERITIES: frozenset[Severity] = frozenset(
    {Severity.CRITICAL, Severity.HIGH}
)


def get_patterns() -> tuple[DangerousPattern, ...]:
    """Return the full set of built-in dangerous patterns."""
    return DANGEROUS_PATTERNS


def get_critical_patterns() -> tuple[DangerousPattern, ...]:
    """Return only CRITICAL severity patterns (always blocked)."""
    return tuple(p for p in DANGEROUS_PATTERNS if p.severity == Severity.CRITICAL)


def is_overridable(pattern: DangerousPattern) -> bool:
    """
    Return ``True`` if this pattern can be overridden by a user allowlist.

    CRITICAL and HIGH severity patterns are never overridable.

    Args:
        pattern: The :class:`DangerousPattern` to test.

    Returns:
        ``True`` only for MEDIUM and LOW severity patterns.
    """
    return pattern.severity not in _NON_OVERRIDABLE_SEVERITIES
