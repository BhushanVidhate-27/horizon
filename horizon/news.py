"""SerpApi sky-news enrichment (optional).

Fetches recent astronomy / rare-sky-event headlines so the daily alert can add
"in the news" context (e.g. a comet, an aurora watch, a rocket launch). When
``SERPAPI_API_KEY`` is missing this returns an empty list and the app behaves
exactly the same minus the news lines.
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx

from .config import get_settings

log = logging.getLogger("horizon.news")

SERPAPI_URL = "https://serpapi.com/search"


def fetch_sky_news(max_results: int = 3) -> list[str]:
    settings = get_settings()
    if not settings.has_serpapi:
        return []

    month = datetime.now().strftime("%B %Y")
    params = {
        "engine": "google",
        "q": f"astronomy visible tonight {month} sky event",
        "api_key": settings.serpapi_api_key,
        "num": max_results,
    }
    try:
        resp = httpx.get(SERPAPI_URL, params=params, timeout=settings.request_timeout)
        resp.raise_for_status()
        payload = resp.json()
    except httpx.HTTPError as exc:
        log.warning("SerpApi fetch failed: %s", exc)
        return []

    headlines: list[str] = []
    for item in (payload.get("organic_results") or [])[:max_results]:
        title = (item.get("title") or "").strip()
        if title:
            headlines.append(title)
    return headlines
