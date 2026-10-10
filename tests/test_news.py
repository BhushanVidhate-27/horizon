"""SerpApi sky-news enrichment (offline; HTTP monkeypatched)."""

import httpx

from horizon import news
from horizon.config import get_settings


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_no_key_returns_empty():
    # The autouse fixture clears SERPAPI_API_KEY.
    assert news.fetch_sky_news() == []


def test_parses_and_limits_titles(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "k")
    get_settings.cache_clear()
    payload = {
        "organic_results": [
            {"title": "Comet visible"},
            {"title": "Aurora watch"},
            {"no_title": True},
            {"title": "   "},
            {"title": "Meteor shower"},
        ]
    }
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(payload))
    assert news.fetch_sky_news(max_results=2) == ["Comet visible", "Aurora watch"]


def test_http_failure_returns_empty(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "k")
    get_settings.cache_clear()

    def boom(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "get", boom)
    assert news.fetch_sky_news() == []
