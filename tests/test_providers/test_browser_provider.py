"""Unit tests for BrowserProvider."""

import httpx

from providers.browser import BrowserProvider


class TestBrowserProvider:
    def test_open_url_invalid_protocol(self):
        provider = BrowserProvider()
        res = provider.open_url("ftp://example.com")
        assert res["status"] == "error"
        assert res["code"] == "ERROR"

    def test_open_url_valid(self, monkeypatch):
        monkeypatch.setattr("webbrowser.open", lambda url: True)
        provider = BrowserProvider()
        res = provider.open_url("https://example.com")
        assert res["status"] == "success"
        assert res["data"]["url"] == "https://example.com"
        assert res["data"]["opened"] is True

    def test_fetch_page(self, monkeypatch):
        class MockResponse:
            def __init__(self):
                self.status_code = 200
                self.url = "https://example.com"
                self.headers = {"content-type": "text/html"}
                self.text = (
                    "<html><head><title>Test</title></head><body><h1>Hello</h1></body></html>"
                )

        class MockClient:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def get(self, url):
                return MockResponse()

        monkeypatch.setattr(httpx, "Client", MockClient)

        provider = BrowserProvider()
        res = provider.fetch_page("https://example.com")
        assert res["status"] == "success"
        assert res["data"]["status_code"] == 200
        assert "Hello" in res["data"]["content"]

    def test_extract_text(self, monkeypatch):
        class MockResponse:
            status_code = 200
            url = "https://example.com"
            text = "<html><head><title>My Title</title></head><body><script>var a=1;</script><p>Clean Text</p></body></html>"

        class MockClient:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def get(self, url):
                return MockResponse()

        monkeypatch.setattr(httpx, "Client", MockClient)

        provider = BrowserProvider()
        res = provider.extract_text("https://example.com")
        assert res["status"] == "success"
        assert res["data"]["title"] == "My Title"
        assert "Clean Text" in res["data"]["text"]
        assert "var a=1" not in res["data"]["text"]

    def test_check_url(self, monkeypatch):
        class MockResponse:
            def __init__(self):
                self.status_code = 200
                self.url = "https://example.com"
                self.headers = {
                    "content-type": "text/html",
                    "content-length": "100",
                    "server": "nginx",
                }
                self.is_success = True

        class MockClient:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def head(self, url):
                return MockResponse()

        monkeypatch.setattr(httpx, "Client", MockClient)

        provider = BrowserProvider()
        res = provider.check_url("https://example.com")
        assert res["status"] == "success"
        assert res["data"]["status_code"] == 200
        assert res["data"]["content_type"] == "text/html"
