"""The Horizon agent: orchestrates the daily-alert pipeline.

This is the single entry point used by both the CLI and the web API.

Sentry (partner category: **Best Use of Sentry**) wraps the whole pipeline with
agent tracing: one transaction per alert, a span per stage (location, weather,
sky, news, narration, voice, storage) and captured exceptions. When
``SENTRY_DSN`` is unset everything runs with no-op shims.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from . import narrator, news, voice, weather
from . import sky as sky_mod
from .config import get_settings
from .geocode import resolve_location
from .llm import LLMClient
from .models import AlertRequest, DailyAlert, ProviderStatus, SkyEvent
from .storage import Storage

log = logging.getLogger("horizon.agent")

_sentry_ready = False


def init_sentry() -> bool:
    """Initialise Sentry if configured. Safe to call multiple times."""
    global _sentry_ready
    if _sentry_ready:
        return True
    settings = get_settings()
    if not settings.has_sentry:
        return False
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            environment=settings.sentry_environment,
            release=f"horizon@{settings.app_version}",
        )
        _sentry_ready = True
        log.info("Sentry tracing enabled.")
        return True
    except Exception as exc:
        log.warning("Sentry init failed: %s", exc)
        return False


@contextmanager
def _span(op: str, description: str) -> Iterator[None]:
    """A Sentry span, or a no-op when Sentry is not installed/configured."""
    if not _sentry_ready:
        yield
        return
    try:
        import sentry_sdk

        with sentry_sdk.start_span(op=op, description=description):
            yield
    except Exception:
        yield


def build_daily_alert(
    request: AlertRequest,
    *,
    store: Storage | None = None,
    llm: LLMClient | None = None,
) -> DailyAlert:
    """Run the full pipeline and return a narrated :class:`DailyAlert`."""
    sentry_on = init_sentry()
    store = store or Storage()
    llm = llm or LLMClient()

    providers = ProviderStatus(
        sentry=sentry_on,
        mongodb=store.backend == "mongodb",
        hosting="digitalocean/render" if _looks_hosted() else "local",
        llm_provider=llm.provider if llm.available else None,
    )

    # Prefer a stored preference for a named city, then fall back to geocoding.
    with _span("location", "resolve location"):
        location = None
        if request.city:
            location = store.get_location_pref(request.city)
        if location is None:
            location = resolve_location(request.city, request.latitude, request.longitude)
        if request.city:
            store.save_location_pref(request.city, location)

    with _span("sky", "compute sky events"):
        report = sky_mod.compute_sky_report(location)

    with _span("weather", "fetch + score weather"):
        window, hourly = weather.get_weather(location, daylight=(report.sunrise, report.sunset))

    with _span("news", "fetch sky news"):
        headlines = news.fetch_sky_news()
        providers.serpapi = bool(headlines)
        for headline in headlines:
            report.events.append(SkyEvent(kind="news", label="Sky news", detail=headline))

    weather_summary = _weather_summary(window)
    now_local = datetime.now(location_tz(location))

    alert = DailyAlert(
        location=location,
        generated_at=now_local,
        generated_for_date=now_local.strftime("%Y-%m-%d"),
        headline="",
        message="",
        nudge="",
        weather_summary=weather_summary,
        best_window=window,
        hourly=hourly,
        sky_report=report,
        news=headlines,
        providers=providers,
    )

    with _span("narration", "compose alert"):
        alert = narrator.compose(alert, llm=llm, use_llm=request.use_llm)

    if request.speak:
        with _span("voice", "ElevenLabs narration"):
            spoken = f"{alert.headline}. {alert.message} {alert.nudge}"
            audio = voice.synthesize(spoken)
            if audio:
                alert.audio_url = audio
                alert.providers.elevenlabs = True

    with _span("storage", "persist alert"):
        try:
            store.save_alert(alert)
        except Exception as exc:
            log.warning("Failed to persist alert: %s", exc)

    return alert


def location_tz(location, default="UTC"):
    from zoneinfo import ZoneInfo

    try:
        return ZoneInfo(location.timezone or default)
    except Exception:  # pragma: no cover
        return ZoneInfo("UTC")


def _weather_summary(window) -> str:
    if window is None:
        return "Weather data unavailable."
    return (
        f"{window.summary.capitalize()}, {window.temperature_c:.0f}°C "
        f"(feels {window.feels_like_c:.0f}°C), {window.precipitation_probability}% "
        f"chance of rain, wind {window.wind_kph:.0f} km/h, {window.cloud_cover}% cloud."
    )


def _looks_hosted() -> bool:
    import os

    return any(
        os.getenv(var) for var in ("RENDER", "RENDER_EXTERNAL_URL", "DIGITALOCEAN_APP_ID", "DYNO")
    )
