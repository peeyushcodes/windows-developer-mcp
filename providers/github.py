"""
GitHub provider for Windows Developer MCP.

Provides GitHub repository management via the GitHub REST API.
The provider gracefully degrades when no GITHUB_TOKEN is available —
unauthenticated requests are attempted but subject to rate limiting.

Tools:
    github_repo_info        — Repository metadata
    github_list_issues      — List repository issues
    github_get_issue        — Get a specific issue
    github_create_issue     — Create an issue
    github_list_prs         — List pull requests
    github_get_pr           — Get a specific PR
    github_list_releases    — List releases
    github_search_repos     — Search GitHub repositories
    github_rate_limit       — Check API rate limit status
    github_auth_status      — Check authentication status
"""

from __future__ import annotations

import logging
import os
from typing import Any

from providers.base import BaseProvider, tool
from utils.helpers import Timer
from utils.json_utils import (
    confirmation_required,
    success,
)
from utils.json_utils import (
    error as make_error,
)

logger = logging.getLogger(__name__)

_GITHUB_API_BASE = "https://api.github.com"


class GitHubProvider(BaseProvider):
    """
    Provides GitHub REST API integration.

    Authentication is via a ``GITHUB_TOKEN`` environment variable. Without
    a token, all calls are unauthenticated and subject to a 60 req/hour
    rate limit. With a token, the limit is 5,000 req/hour.

    This provider **never** raises on missing token — it degrades gracefully.
    """

    name = "github"
    description = "GitHub repos, issues, PRs, releases, and repository search."

    def _headers(self) -> dict[str, str]:
        """Build request headers, including auth token if available."""
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """Perform an authenticated GET request to the GitHub API."""
        import httpx

        url = f"{_GITHUB_API_BASE}{endpoint}"
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            response = client.get(url, headers=self._headers(), params=params or {})
            response.raise_for_status()
            return response.json()

    def _post(self, endpoint: str, body: dict[str, Any]) -> Any:
        """Perform an authenticated POST request to the GitHub API."""
        import httpx

        url = f"{_GITHUB_API_BASE}{endpoint}"
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            response = client.post(url, headers=self._headers(), json=body)
            response.raise_for_status()
            return response.json()

    # ------------------------------------------------------------------
    # Auth / Rate Limit
    # ------------------------------------------------------------------

    @tool
    def github_auth_status(self) -> dict[str, Any]:
        """
        Check GitHub authentication status and token validity.

        Returns whether a token is configured and (if so) the authenticated
        user's login name.

        Returns:
            A dict with keys: status, data (authenticated, token_present, user).

        Examples:
            github_auth_status()
        """
        with Timer() as t:
            token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
            if not token:
                return success(
                    {
                        "authenticated": False,
                        "token_present": False,
                        "user": None,
                        "message": (
                            "No GITHUB_TOKEN found. Set the GITHUB_TOKEN environment variable "
                            "to enable authenticated GitHub API access (5,000 req/hour)."
                        ),
                    },
                    tool="github_auth_status",
                    duration_ms=t.elapsed_ms,
                )
            try:
                data = self._get("/user")
                return success(
                    {
                        "authenticated": True,
                        "token_present": True,
                        "user": data.get("login"),
                        "name": data.get("name"),
                        "email": data.get("email"),
                    },
                    tool="github_auth_status",
                    duration_ms=t.elapsed_ms,
                )
            except Exception as exc:
                return make_error(
                    f"Token validation failed: {exc}",
                    tool="github_auth_status",
                    code="AUTH_ERROR",
                )

    @tool
    def github_rate_limit(self) -> dict[str, Any]:
        """
        Check the current GitHub API rate limit status.

        Returns:
            A dict with keys: status, data (core, search, and graphql limits).

        Examples:
            github_rate_limit()
        """
        with Timer() as t:
            try:
                data = self._get("/rate_limit")
                resources = data.get("resources", {})
                return success(
                    {
                        "core": resources.get("core", {}),
                        "search": resources.get("search", {}),
                        "graphql": resources.get("graphql", {}),
                    },
                    tool="github_rate_limit",
                    duration_ms=t.elapsed_ms,
                )
            except Exception as exc:
                return make_error(str(exc), tool="github_rate_limit", code="API_ERROR")

    # ------------------------------------------------------------------
    # Repositories
    # ------------------------------------------------------------------

    @tool
    def github_repo_info(self, owner: str, repo: str) -> dict[str, Any]:
        """
        Return metadata for a GitHub repository.

        Args:
            owner: The repository owner (user or org).
            repo:  The repository name.

        Returns:
            A dict with keys: status, data (name, description, stars, forks, etc.).

        Examples:
            github_repo_info("microsoft", "vscode")
            github_repo_info("python", "cpython")
        """
        with Timer() as t:
            try:
                data = self._get(f"/repos/{owner}/{repo}")
                return success(
                    {
                        "full_name": data.get("full_name"),
                        "description": data.get("description"),
                        "stars": data.get("stargazers_count"),
                        "forks": data.get("forks_count"),
                        "open_issues": data.get("open_issues_count"),
                        "language": data.get("language"),
                        "license": data.get("license", {}).get("spdx_id")
                        if data.get("license")
                        else None,
                        "default_branch": data.get("default_branch"),
                        "url": data.get("html_url"),
                        "clone_url": data.get("clone_url"),
                        "private": data.get("private"),
                        "archived": data.get("archived"),
                        "created_at": data.get("created_at"),
                        "updated_at": data.get("updated_at"),
                        "pushed_at": data.get("pushed_at"),
                        "topics": data.get("topics", []),
                    },
                    tool="github_repo_info",
                    duration_ms=t.elapsed_ms,
                )
            except Exception as exc:
                return make_error(str(exc), tool="github_repo_info", code="API_ERROR")

    @tool
    def github_search_repos(
        self,
        query: str,
        sort: str = "stars",
        order: str = "desc",
        limit: int = 10,
    ) -> dict[str, Any]:
        """
        Search GitHub repositories.

        Args:
            query: GitHub search query (supports qualifiers like language:python).
            sort:  Sort field — "stars", "forks", "updated". Default: "stars".
            order: Sort order — "asc" or "desc". Default: "desc".
            limit: Maximum results (1–30). Default: 10.

        Returns:
            A dict with keys: status, data (total_count, items list).

        Examples:
            github_search_repos("mcp server windows")
            github_search_repos("language:python fastmcp")
            github_search_repos("topic:ai-assistant stars:>100")
        """
        limit = max(1, min(limit, 30))
        with Timer() as t:
            try:
                data = self._get(
                    "/search/repositories",
                    params={"q": query, "sort": sort, "order": order, "per_page": limit},
                )
                items = [
                    {
                        "full_name": r.get("full_name"),
                        "description": r.get("description", ""),
                        "stars": r.get("stargazers_count"),
                        "language": r.get("language"),
                        "url": r.get("html_url"),
                        "updated_at": r.get("updated_at"),
                    }
                    for r in data.get("items", [])
                ]
                return success(
                    {
                        "query": query,
                        "total_count": data.get("total_count", 0),
                        "returned": len(items),
                        "items": items,
                    },
                    tool="github_search_repos",
                    duration_ms=t.elapsed_ms,
                )
            except Exception as exc:
                return make_error(str(exc), tool="github_search_repos", code="API_ERROR")

    # ------------------------------------------------------------------
    # Issues
    # ------------------------------------------------------------------

    @tool
    def github_list_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        limit: int = 20,
        label: str = "",
    ) -> dict[str, Any]:
        """
        List issues for a GitHub repository.

        Args:
            owner:  Repository owner.
            repo:   Repository name.
            state:  Issue state — "open", "closed", or "all". Default: "open".
            limit:  Maximum issues to return (1–100). Default: 20.
            label:  Filter by label name.

        Returns:
            A dict with keys: status, data (count, issues list).

        Examples:
            github_list_issues("microsoft", "vscode")
            github_list_issues("python", "cpython", state="closed", limit=5)
        """
        limit = max(1, min(limit, 100))
        with Timer() as t:
            try:
                params: dict[str, Any] = {"state": state, "per_page": limit}
                if label:
                    params["labels"] = label
                data = self._get(f"/repos/{owner}/{repo}/issues", params=params)
                # Filter out pull requests (GitHub API returns them as issues too)
                issues = [
                    {
                        "number": i.get("number"),
                        "title": i.get("title"),
                        "state": i.get("state"),
                        "author": i.get("user", {}).get("login"),
                        "labels": [lbl.get("name") for lbl in i.get("labels", [])],
                        "created_at": i.get("created_at"),
                        "updated_at": i.get("updated_at"),
                        "url": i.get("html_url"),
                        "comments": i.get("comments"),
                    }
                    for i in data
                    if not i.get("pull_request")
                ]
                return success(
                    {"count": len(issues), "issues": issues},
                    tool="github_list_issues",
                    duration_ms=t.elapsed_ms,
                )
            except Exception as exc:
                return make_error(str(exc), tool="github_list_issues", code="API_ERROR")

    @tool
    def github_get_issue(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        """
        Get a specific GitHub issue by number.

        Args:
            owner:  Repository owner.
            repo:   Repository name.
            number: Issue number.

        Returns:
            A dict with keys: status, data (issue details including body).

        Examples:
            github_get_issue("microsoft", "vscode", 12345)
        """
        with Timer() as t:
            try:
                data = self._get(f"/repos/{owner}/{repo}/issues/{number}")
                return success(
                    {
                        "number": data.get("number"),
                        "title": data.get("title"),
                        "body": data.get("body", ""),
                        "state": data.get("state"),
                        "author": data.get("user", {}).get("login"),
                        "assignees": [a.get("login") for a in data.get("assignees", [])],
                        "labels": [lbl.get("name") for lbl in data.get("labels", [])],
                        "milestone": data.get("milestone", {}).get("title")
                        if data.get("milestone")
                        else None,
                        "created_at": data.get("created_at"),
                        "updated_at": data.get("updated_at"),
                        "comments": data.get("comments"),
                        "url": data.get("html_url"),
                    },
                    tool="github_get_issue",
                    duration_ms=t.elapsed_ms,
                )
            except Exception as exc:
                return make_error(str(exc), tool="github_get_issue", code="API_ERROR")

    @tool
    def github_create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str = "",
        labels: str = "",
        confirm: bool = False,
    ) -> dict[str, Any]:
        """
        Create a new GitHub issue.

        Requires a GITHUB_TOKEN with issue write permissions and explicit
        confirmation when required by config.

        Args:
            owner:  Repository owner.
            repo:   Repository name.
            title:  Issue title.
            body:   Issue body (Markdown supported).
            labels: Comma-separated label names.
            confirm: Set to True to confirm.

        Returns:
            A dict with keys: status, data (issue number, url).

        Examples:
            github_create_issue("me", "my-repo", "Bug: login broken", confirm=True)
        """
        from core.exceptions import ConfirmationRequiredError
        from security.permissions import PermissionManager

        pm = PermissionManager()
        if pm.requires_confirmation("github_create_issue"):
            try:
                pm.assert_confirmed(action=f"github create issue: {title!r}", confirm=confirm)
            except ConfirmationRequiredError:
                return confirmation_required(
                    f"github create issue: {title!r}", tool="github_create_issue"
                )

        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            return make_error(
                "GITHUB_TOKEN is required to create issues. "
                "Set the GITHUB_TOKEN environment variable.",
                tool="github_create_issue",
                code="NO_AUTH",
            )

        with Timer() as t:
            try:
                payload: dict[str, Any] = {"title": title}
                if body:
                    payload["body"] = body
                if labels:
                    payload["labels"] = [item.strip() for item in labels.split(",") if item.strip()]

                data = self._post(f"/repos/{owner}/{repo}/issues", payload)
                return success(
                    {
                        "number": data.get("number"),
                        "title": data.get("title"),
                        "url": data.get("html_url"),
                        "state": data.get("state"),
                    },
                    tool="github_create_issue",
                    duration_ms=t.elapsed_ms,
                )
            except Exception as exc:
                return make_error(str(exc), tool="github_create_issue", code="API_ERROR")

    # ------------------------------------------------------------------
    # Pull Requests
    # ------------------------------------------------------------------

    @tool
    def github_list_prs(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        limit: int = 20,
    ) -> dict[str, Any]:
        """
        List pull requests for a repository.

        Args:
            owner: Repository owner.
            repo:  Repository name.
            state: "open", "closed", or "all". Default: "open".
            limit: Maximum PRs to return (1–100). Default: 20.

        Returns:
            A dict with keys: status, data (count, prs list).

        Examples:
            github_list_prs("microsoft", "vscode")
            github_list_prs("python", "cpython", state="closed")
        """
        limit = max(1, min(limit, 100))
        with Timer() as t:
            try:
                data = self._get(
                    f"/repos/{owner}/{repo}/pulls",
                    params={"state": state, "per_page": limit},
                )
                prs = [
                    {
                        "number": pr.get("number"),
                        "title": pr.get("title"),
                        "state": pr.get("state"),
                        "author": pr.get("user", {}).get("login"),
                        "base": pr.get("base", {}).get("ref"),
                        "head": pr.get("head", {}).get("ref"),
                        "draft": pr.get("draft"),
                        "created_at": pr.get("created_at"),
                        "updated_at": pr.get("updated_at"),
                        "url": pr.get("html_url"),
                        "mergeable": pr.get("mergeable"),
                    }
                    for pr in data
                ]
                return success(
                    {"count": len(prs), "prs": prs},
                    tool="github_list_prs",
                    duration_ms=t.elapsed_ms,
                )
            except Exception as exc:
                return make_error(str(exc), tool="github_list_prs", code="API_ERROR")

    @tool
    def github_get_pr(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        """
        Get a specific pull request by number.

        Args:
            owner:  Repository owner.
            repo:   Repository name.
            number: PR number.

        Returns:
            A dict with keys: status, data (full PR details including body, diff stats).

        Examples:
            github_get_pr("microsoft", "vscode", 200000)
        """
        with Timer() as t:
            try:
                data = self._get(f"/repos/{owner}/{repo}/pulls/{number}")
                return success(
                    {
                        "number": data.get("number"),
                        "title": data.get("title"),
                        "body": data.get("body", ""),
                        "state": data.get("state"),
                        "author": data.get("user", {}).get("login"),
                        "base": data.get("base", {}).get("ref"),
                        "head": data.get("head", {}).get("ref"),
                        "draft": data.get("draft"),
                        "merged": data.get("merged"),
                        "mergeable": data.get("mergeable"),
                        "additions": data.get("additions"),
                        "deletions": data.get("deletions"),
                        "changed_files": data.get("changed_files"),
                        "commits": data.get("commits"),
                        "created_at": data.get("created_at"),
                        "url": data.get("html_url"),
                    },
                    tool="github_get_pr",
                    duration_ms=t.elapsed_ms,
                )
            except Exception as exc:
                return make_error(str(exc), tool="github_get_pr", code="API_ERROR")

    # ------------------------------------------------------------------
    # Releases
    # ------------------------------------------------------------------

    @tool
    def github_list_releases(self, owner: str, repo: str, limit: int = 10) -> dict[str, Any]:
        """
        List releases for a repository.

        Args:
            owner: Repository owner.
            repo:  Repository name.
            limit: Maximum releases to return (1–30). Default: 10.

        Returns:
            A dict with keys: status, data (count, releases list).

        Examples:
            github_list_releases("microsoft", "vscode")
            github_list_releases("python", "cpython", limit=5)
        """
        limit = max(1, min(limit, 30))
        with Timer() as t:
            try:
                data = self._get(
                    f"/repos/{owner}/{repo}/releases",
                    params={"per_page": limit},
                )
                releases = [
                    {
                        "tag_name": r.get("tag_name"),
                        "name": r.get("name"),
                        "draft": r.get("draft"),
                        "prerelease": r.get("prerelease"),
                        "published_at": r.get("published_at"),
                        "url": r.get("html_url"),
                        "assets": len(r.get("assets", [])),
                    }
                    for r in data
                ]
                return success(
                    {"count": len(releases), "releases": releases},
                    tool="github_list_releases",
                    duration_ms=t.elapsed_ms,
                )
            except Exception as exc:
                return make_error(str(exc), tool="github_list_releases", code="API_ERROR")
