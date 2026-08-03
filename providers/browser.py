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

        Args:
            url: The HTTP or HTTPS URL to open.

        Returns:
            Standard success or error response dictionary.
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
        Fetch static web page content over HTTP/HTTPS.

        Args:
            url: The URL to fetch.
            timeout: Request timeout in seconds (default: 30).

        Returns:
            Dictionary with status code, response headers, and content snippet.
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
        Fetch a web page and extract human-readable body text.

        Strips script, style, and HTML markup tags to produce clean text.

        Args:
            url: The URL to extract text from.
            max_chars: Maximum characters of text to return (default: 10000).

        Returns:
            Dictionary with extracted page title and body text.
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
        Send an HTTP HEAD request to verify URL accessibility and inspect response headers.

        Args:
            url: The URL to inspect.

        Returns:
            Dictionary with status code, server header, content type, and length.
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
