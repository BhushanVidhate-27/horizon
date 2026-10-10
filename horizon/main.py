"""FastAPI web app for Horizon.

Run locally:
    uvicorn horizon.main:app --reload

Endpoints:
    GET  /                 -> single-page web UI
    GET  /api/health       -> service + integration status
    POST /api/alert        -> build a daily alert (full control)
    GET  /api/alert        -> build a daily alert via query string
    GET  /api/history      -> recent stored alerts
    GET  /api/search       -> search stored alerts
    GET  /api/stats        -> storage backend statistics
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .agent import build_daily_alert, init_sentry
from .config import get_settings
from .events import upcoming_events
from .geocode import geocode_city
from .llm import LLMClient
from .models import AlertRequest, DailyAlert
from .storage import Storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_sentry()
    yield


app = FastAPI(
    title="Horizon API",
    version=settings.app_version,
    description="Daily outside alert & sky event planner (Hacktoberfest 2026, Touch Grass).",
    lifespan=lifespan,
)

STATIC_DIR = Path(__file__).parent / "static"
AUDIO_DIR = Path(settings.cache_dir) / "audio"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")

_store: Storage | None = None
_llm: LLMClient | None = None


def store() -> Storage:
    global _store
    if _store is None:
        _store = Storage()
    return _store


def llm() -> LLMClient:
    """A process-wide LLM client, so health checks don't re-probe Ollama."""
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    client = llm()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "integrations": {
            "gemma": client.available,
            "gemma_provider": client.provider,
            "elevenlabs": settings.has_elevenlabs,
            "mongodb": settings.has_mongodb,
            "serpapi": settings.has_serpapi,
            "sentry": settings.has_sentry,
        },
        "storage": store().stats(),
    }


@app.get("/api/geocode")
def api_geocode(city: str = Query(..., min_length=1)) -> dict:
    location = geocode_city(city)
    if location is None:
        raise HTTPException(status_code=404, detail=f"Could not find '{city}'")
    return location.model_dump()


@app.post("/api/alert", response_model=DailyAlert)
def api_alert(request: AlertRequest) -> DailyAlert:
    return build_daily_alert(request, store=store())


@app.get("/api/alert", response_model=DailyAlert)
def api_alert_query(
    city: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    speak: bool = False,
    use_llm: bool = True,
) -> DailyAlert:
    request = AlertRequest(
        city=city, latitude=latitude, longitude=longitude, speak=speak, use_llm=use_llm
    )
    return build_daily_alert(request, store=store())


@app.get("/api/history")
def api_history(limit: int = 5, city: str | None = None) -> dict:
    return {"alerts": store().recent_alerts(limit=limit, location_name=city)}


@app.get("/api/search")
def api_search(
    q: str = Query(..., min_length=1), limit: int = Query(default=5, ge=1, le=50)
) -> dict:
    """Search the alert history (the hook for Atlas Vector Search)."""
    return {"query": q, "results": store().search_history(q, limit=limit)}


@app.get("/api/stats")
def api_stats() -> dict:
    return store().stats()


@app.get("/api/events")
def api_events(days: int = Query(default=90, ge=7, le=365)) -> dict:
    """Notable sky events for the calendar (importance 2+ deserves a highlight)."""
    return {"events": [event.model_dump() for event in upcoming_events(days=days)]}


def main() -> None:  # pragma: no cover - convenience runner
    import uvicorn

    uvicorn.run("horizon.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":  # pragma: no cover
    main()
