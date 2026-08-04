"""
Browser Provider for Windows Developer MCP.

Provides tools for web page fetching, HTML text extraction, URL status checks,
and opening web pages in the default system browser.
"""

from __future__ import annotations

import logging
import re
from typing import Any
import webbrowser

import httpx

from providers.base import BaseProvider, tool
from utils.json_utils import error as make_error
from utils.json_utils import success as make_success

logger = logging.getLogger(__name__)


class BrowserProvider(BaseProvider):
    """Provider for web and browser interaction tools."""

    name = "browser"
    description = (
        "Web page fetching, text extraction, URL checking, and system browser integration."
    )

    @tool
    def open_url(self, url: str) -> dict[str, Any]:
        """
        Open a URL in the default system web browser.

        Launches the OS default browser (e.g. Chrome, Edge) as a side effect.
        The browser opens in a new window or tab; this tool does not wait
        for the page to load or the browser to close.

        Args:
            url: The full HTTP or HTTPS URL to open (e.g. "https://example.com").
                 Only http:// and https:// schemes are accepted; ftp://, file://,
                 and other schemes are rejected.

        Returns:
            A dict with keys: status ("success"/"error"), data.url, data.opened (bool).

        Raises:
            error: If the URL scheme is not http/https, or if the OS reports
                   no default browser is configured.

        Examples:
            open_url("https://docs.python.org")
            open_url("https://github.com/peeyushcodes/windows-developer-mcp")
        """
        if not url.startswith(("http://", "https://")):
            return make_error(
                "Invalid URL protocol. Only http:// and https:// URLs are allowed.", tool="open_url"
            )

        try:
            opened = webbrowser.open(url)
            return make_success(
                {"url": url, "opened": opened},
                tool="open_url",
            )
        except Exception as exc:
            logger.exception("Failed to open URL: %s", url)
            return make_error(f"Failed to open URL '{url}': {exc}", tool="open_url")

    @tool
    def fetch_page(self, url: str, timeout: int = 30) -> dict[str, Any]:
        """
        Fetch the raw HTML/text content of a web page over HTTP/HTTPS.

        Follows redirects automatically. Returns up to 50,000 characters of
        response body. Does NOT execute JavaScript — use a headless browser
        for JS-rendered pages. Makes a real outbound network request.

        Args:
            url:     The full HTTP or HTTPS URL to fetch.
            timeout: Request timeout in seconds. Default: 30. Range: 1–120.

        Returns:
            A dict with keys: status, data.url (final URL after redirects),
            data.status_code, data.headers, data.content (up to 50 000 chars),
            data.content_length (total chars before truncation).

        Raises:
            error: On network failure, DNS error, or invalid URL scheme.

        Examples:
            fetch_page("https://example.com")
            fetch_page("https://api.github.com", timeout=10)
        """
        if not url.startswith(("http://", "https://")):
            return make_error(
                "Invalid URL protocol. Only http:// and https:// URLs are allowed.",
                tool="fetch_page",
            )

        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                response = client.get(url)
                headers_dict = dict(response.headers)
                return make_success(
                    {
                        "url": str(response.url),
                        "status_code": response.status_code,
                        "headers": headers_dict,
                        "content": response.text[:50000],
                        "content_length": len(response.text),
                    },
                    tool="fetch_page",
                )
        except Exception as exc:
            logger.exception("Failed to fetch web page: %s", url)
            return make_error(f"Failed to fetch '{url}': {exc}", tool="fetch_page")

    @tool
    def extract_text(self, url: str, max_chars: int = 10000) -> dict[str, Any]:
        """
        Fetch a web page and extract clean, human-readable body text.

        Strips <script>, <style>, HTML comments, and all remaining HTML tags
        to produce plain text suitable for summarisation or search. Does NOT
        execute JavaScript — dynamically rendered content will not appear.
        Makes a real outbound network request.

        Args:
            url:       The full HTTP or HTTPS URL to extract text from.
            max_chars: Maximum characters of extracted text to return.
                       Default: 10 000. The full character count is always
                       reported in data.character_count.

        Returns:
            A dict with keys: status, data.url, data.status_code, data.title
            (page <title>), data.text (extracted plain text), data.character_count
            (total before truncation), data.is_truncated (bool).

        Raises:
            error: On network failure or invalid URL scheme.

        Examples:
            extract_text("https://en.wikipedia.org/wiki/Python")
            extract_text("https://news.ycombinator.com", max_chars=5000)
        """
        if not url.startswith(("http://", "https://")):
            return make_error(
                "Invalid URL protocol. Only http:// and https:// URLs are allowed.",
                tool="extract_text",
            )

        try:
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                response = client.get(url)
                html = response.text

                # Extract title
                title_match = re.search(
                    r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL
                )
                title = title_match.group(1).strip() if title_match else ""

                # Remove script and style tags
                clean_html = re.sub(
                    r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.IGNORECASE | re.DOTALL
                )
                # Remove HTML comments
                clean_html = re.sub(r"<!--.*?-->", "", clean_html, flags=re.DOTALL)
                # Remove all remaining HTML tags
                text = re.sub(r"<[^>]+>", " ", clean_html)
                # Collapse whitespace
                text = re.sub(r"\s+", " ", text).strip()

                truncated_text = text[:max_chars]

                return make_success(
                    {
                        "url": str(response.url),
                        "status_code": response.status_code,
                        "title": title,
                        "text": truncated_text,
                        "character_count": len(text),
                        "is_truncated": len(text) > max_chars,
                    },
                    tool="extract_text",
                )
        except Exception as exc:
            logger.exception("Failed to extract text from URL: %s", url)
            return make_error(f"Failed to extract text from '{url}': {exc}", tool="extract_text")

    @tool
    def check_url(self, url: str) -> dict[str, Any]:
        """
        Probe a URL with an HTTP HEAD request to verify accessibility and inspect headers.

        Uses HEAD to avoid downloading the response body. Automatically falls
        back to a GET request if the server does not support HEAD (405 or network
        error). Makes a real outbound network request with a 15-second timeout.

        Args:
            url: The full HTTP or HTTPS URL to check.

        Returns:
            A dict with keys: status, data.url (final URL after redirects),
            data.status_code, data.content_type, data.content_length,
            data.server, data.is_success (bool, True for 2xx status codes).

        Raises:
            error: On network failure, DNS error, or invalid URL scheme.

        Examples:
            check_url("https://example.com")
            check_url("https://github.com/peeyushcodes/windows-developer-mcp")
        """
        if not url.startswith(("http://", "https://")):
            return make_error(
                "Invalid URL protocol. Only http:// and https:// URLs are allowed.",
                tool="check_url",
            )

        try:
            with httpx.Client(timeout=15, follow_redirects=True) as client:
                try:
                    response = client.head(url)
                except httpx.HTTPError:
                    # Fallback to GET if HEAD method is not supported by target server
                    response = client.get(url)

                return make_success(
                    {
                        "url": str(response.url),
                        "status_code": response.status_code,
                        "content_type": response.headers.get("content-type", ""),
                        "content_length": response.headers.get("content-length", "unknown"),
                        "server": response.headers.get("server", ""),
                        "is_success": response.is_success,
                    },
                    tool="check_url",
                )
        except Exception as exc:
            logger.exception("Failed to check URL: %s", url)
            return make_error(f"Failed to check URL '{url}': {exc}", tool="check_url")
