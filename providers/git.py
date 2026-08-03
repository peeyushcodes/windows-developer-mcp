"""
Git provider for Windows Developer MCP.

Exposes a comprehensive set of Git operations as MCP tools. All commands
are executed via the full security pipeline. The provider operates in the
current session working directory by default.

Tools:
    git_status        — Working tree status
    git_branch        — List or show branches
    git_log           — Commit history
    git_diff          — Show changes
    git_add           — Stage files
    git_commit        — Create a commit
    git_push          — Push to remote
    git_pull          — Pull from remote
    git_clone         — Clone a repository
    git_checkout      — Switch branches or restore files
    git_create_branch — Create a new branch
    git_stash         — Stash/unstash changes
    git_remote_info   — Show remote configuration
    git_init          — Initialise a new repository
    git_blame         — Show line-by-line authorship
    git_tags          — List tags
"""

from __future__ import annotations

import logging
from typing import Any

from providers.base import BaseProvider, tool

logger = logging.getLogger(__name__)


class GitProvider(BaseProvider):
    """
    Provides Git version control operations.

    All git commands run in the current session working directory.
    Destructive operations (push, commit) respect the ``require_confirmation``
    configuration setting.
    """

    name = "git"
    description = "Git version control: status, branch, log, diff, commit, push, pull, clone."

    # ------------------------------------------------------------------
    # Read Operations
    # ------------------------------------------------------------------

    @tool
    def git_status(self) -> dict[str, Any]:
        """
        Return the current Git working tree status.

        Shows the state of the index and working directory — which files
        are staged, unstaged, or untracked.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            git_status()
        """
        result = self._run_safe("git status", tool_name="git_status")
        return self._shell_response(result, tool_name="git_status")

    @tool
    def git_branch(self, all_branches: bool = False) -> dict[str, Any]:
        """
        List local (or all) branches and indicate the current branch.

        Args:
            all_branches: If True, also lists remote-tracking branches.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            git_branch()
            git_branch(all_branches=True)
        """
        flags = "--all" if all_branches else ""
        result = self._run_safe(f"git branch {flags}".strip(), tool_name="git_branch")
        return self._shell_response(result, tool_name="git_branch")

    @tool
    def git_log(
        self,
        limit: int = 20,
        oneline: bool = True,
        author: str = "",
        since: str = "",
    ) -> dict[str, Any]:
        """
        Return recent commit history.

        Args:
            limit:   Number of commits to show (1–200). Default: 20.
            oneline: If True, show one line per commit. Default: True.
            author:  Filter commits by author name or email.
            since:   Show commits more recent than this date (e.g. "2 weeks ago").

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            git_log()
            git_log(limit=50, oneline=False)
            git_log(author="alice@example.com")
            git_log(since="1 week ago")
        """
        limit = max(1, min(limit, 200))
        parts = ["git log", f"-{limit}"]
        if oneline:
            parts.append("--oneline")
        if author:
            parts.append(f'--author="{author}"')
        if since:
            parts.append(f'--since="{since}"')
        command = " ".join(parts)
        result = self._run_safe(command, tool_name="git_log")
        return self._shell_response(result, tool_name="git_log")

    @tool
    def git_diff(
        self,
        staged: bool = False,
        file_path: str = "",
        stat_only: bool = False,
    ) -> dict[str, Any]:
        """
        Show changes between commits, working tree, or index.

        Args:
            staged:    If True, show staged (indexed) changes only.
            file_path: Restrict diff to a specific file or directory.
            stat_only: If True, show only a summary (files changed, lines).

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            git_diff()
            git_diff(staged=True)
            git_diff(file_path="src/main.py")
            git_diff(stat_only=True)
        """
        parts = ["git diff"]
        if staged:
            parts.append("--cached")
        if stat_only:
            parts.append("--stat")
        if file_path:
            parts.append(f'-- "{file_path}"')
        result = self._run_safe(" ".join(parts), tool_name="git_diff")
        return self._shell_response(result, tool_name="git_diff")

    @tool
    def git_remote_info(self) -> dict[str, Any]:
        """
        Show configured remote repositories and their URLs.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            git_remote_info()
        """
        result = self._run_safe("git remote -v", tool_name="git_remote_info")
        return self._shell_response(result, tool_name="git_remote_info")

    @tool
    def git_blame(self, file_path: str, line_range: str = "") -> dict[str, Any]:
        """
        Show line-by-line authorship information for a file.

        Args:
            file_path:   The file to annotate.
            line_range:  Optional line range in the format "start,end" (e.g. "10,25").

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            git_blame("src/main.py")
            git_blame("src/main.py", line_range="10,25")
        """
        range_arg = f"-L {line_range}" if line_range else ""
        command = f'git blame {range_arg} "{file_path}"'.strip()
        result = self._run_safe(command, tool_name="git_blame")
        return self._shell_response(result, tool_name="git_blame")

    @tool
    def git_tags(self) -> dict[str, Any]:
        """
        List all tags in the repository.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            git_tags()
        """
        result = self._run_safe("git tag --list --sort=-version:refname", tool_name="git_tags")
        return self._shell_response(result, tool_name="git_tags")

    # ------------------------------------------------------------------
    # Write Operations
    # ------------------------------------------------------------------

    @tool
    def git_add(self, files: str = ".") -> dict[str, Any]:
        """
        Stage files for commit.

        Args:
            files: Files or patterns to stage. Use "." to stage all changes.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            git_add()
            git_add("src/main.py")
            git_add("*.py")
        """
        result = self._run_safe(f"git add {files}", tool_name="git_add")
        return self._shell_response(result, tool_name="git_add")

    @tool
    def git_commit(
        self,
        message: str,
        all_changes: bool = False,
        confirm: bool = False,
    ) -> dict[str, Any]:
        """
        Create a commit with the staged changes.

        Requires explicit confirmation when ``security.require_confirmation``
        is enabled in config (default: True).

        Args:
            message:     The commit message. Required.
            all_changes: If True, automatically stage all tracked file changes
                         before committing (equivalent to ``git commit -a``).
            confirm:     Set to True to confirm this destructive operation when
                         confirmation is required by config.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            git_commit("fix: resolve login bug", confirm=True)
            git_commit("feat: add dark mode", all_changes=True, confirm=True)
        """
        from core.exceptions import ConfirmationRequiredError
        from security.permissions import PermissionManager
        from utils.json_utils import confirmation_required

        pm = PermissionManager()
        if pm.requires_confirmation("git_commit"):
            try:
                pm.assert_confirmed(action="git commit", confirm=confirm)
            except ConfirmationRequiredError:
                return confirmation_required("git commit", tool="git_commit")

        flag = "-a " if all_changes else ""
        command = f'git commit {flag}-m "{message}"'
        result = self._run_safe(command, tool_name="git_commit")
        return self._shell_response(result, tool_name="git_commit")

    @tool
    def git_push(
        self,
        remote: str = "origin",
        branch: str = "",
        force: bool = False,
        confirm: bool = False,
    ) -> dict[str, Any]:
        """
        Push commits to a remote repository.

        Requires explicit confirmation when ``security.require_confirmation``
        is enabled in config (default: True).

        Args:
            remote:  The remote name. Default: "origin".
            branch:  The branch to push. Defaults to the current branch.
            force:   If True, force-push (--force-with-lease for safety).
            confirm: Set to True to confirm this potentially destructive
                     operation when confirmation is required by config.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            git_push(confirm=True)
            git_push(remote="origin", branch="main", confirm=True)
        """
        from core.exceptions import ConfirmationRequiredError
        from security.permissions import PermissionManager
        from utils.json_utils import confirmation_required

        pm = PermissionManager()
        if pm.requires_confirmation("git_push"):
            try:
                pm.assert_confirmed(action="git push", confirm=confirm)
            except ConfirmationRequiredError:
                return confirmation_required("git push", tool="git_push")

        force_flag = "--force-with-lease" if force else ""
        branch_arg = branch or ""
        command = f"git push {remote} {branch_arg} {force_flag}".strip()
        result = self._run_safe(command, tool_name="git_push")
        return self._shell_response(result, tool_name="git_push")

    @tool
    def git_pull(self, remote: str = "origin", branch: str = "") -> dict[str, Any]:
        """
        Pull changes from a remote repository.

        Args:
            remote: The remote name. Default: "origin".
            branch: The branch to pull. Defaults to the current tracking branch.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            git_pull()
            git_pull(remote="upstream", branch="main")
        """
        branch_arg = branch or ""
        command = f"git pull {remote} {branch_arg}".strip()
        result = self._run_safe(command, tool_name="git_pull")
        return self._shell_response(result, tool_name="git_pull")

    @tool
    def git_clone(self, url: str, destination: str = "") -> dict[str, Any]:
        """
        Clone a remote repository into a local directory.

        The destination must be within the workspace boundary.

        Args:
            url:         The repository URL (HTTPS or SSH).
            destination: Local directory name or path. Defaults to the repo name.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            git_clone("https://github.com/user/repo.git")
            git_clone("https://github.com/user/repo.git", destination="my-repo")
        """
        dest_arg = f'"{destination}"' if destination else ""
        command = f'git clone "{url}" {dest_arg}'.strip()
        result = self._run_safe(command, tool_name="git_clone")
        return self._shell_response(result, tool_name="git_clone")

    @tool
    def git_checkout(self, branch_or_file: str) -> dict[str, Any]:
        """
        Switch to a branch, or restore a file to its last committed state.

        Args:
            branch_or_file: A branch name to switch to, or a file path to restore.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            git_checkout("main")
            git_checkout("feature/dark-mode")
            git_checkout("src/broken.py")
        """
        result = self._run_safe(f'git checkout "{branch_or_file}"', tool_name="git_checkout")
        return self._shell_response(result, tool_name="git_checkout")

    @tool
    def git_create_branch(self, name: str, from_branch: str = "") -> dict[str, Any]:
        """
        Create a new branch and switch to it.

        Args:
            name:        The new branch name.
            from_branch: Base branch to branch from. Defaults to HEAD.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            git_create_branch("feature/my-feature")
            git_create_branch("hotfix/login-bug", from_branch="main")
        """
        from_arg = f'"{from_branch}"' if from_branch else ""
        command = f'git checkout -b "{name}" {from_arg}'.strip()
        result = self._run_safe(command, tool_name="git_create_branch")
        return self._shell_response(result, tool_name="git_create_branch")

    @tool
    def git_stash(self, action: str = "push", message: str = "") -> dict[str, Any]:
        """
        Stash or restore uncommitted changes.

        Args:
            action:  One of "push" (save), "pop" (restore latest), "list",
                     "drop" (delete latest), or "clear" (delete all).
            message: Optional stash message (only used with action="push").

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            git_stash()                        # Save changes
            git_stash(action="pop")            # Restore last stash
            git_stash(action="push", message="WIP: dark mode")
            git_stash(action="list")
        """
        valid_actions = {"push", "pop", "list", "drop", "clear"}
        if action not in valid_actions:
            return self._error_response(
                f"Invalid stash action {action!r}. "
                f"Must be one of: {', '.join(sorted(valid_actions))}.",
                tool_name="git_stash",
                code="INVALID_ARGUMENT",
            )

        msg_arg = f'"{message}"' if message and action == "push" else ""
        command = f"git stash {action} {msg_arg}".strip()
        result = self._run_safe(command, tool_name="git_stash")
        return self._shell_response(result, tool_name="git_stash")

    @tool
    def git_init(self, path: str = ".") -> dict[str, Any]:
        """
        Initialise a new Git repository.

        The target path must be within the workspace boundary.

        Args:
            path: Directory to initialise. Defaults to the current directory.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            git_init()
            git_init("my-new-project")
        """
        command = f'git init "{path}"' if path != "." else "git init"
        result = self._run_safe(command, tool_name="git_init")
        return self._shell_response(result, tool_name="git_init")
