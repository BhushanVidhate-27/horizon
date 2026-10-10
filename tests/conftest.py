"""Shared pytest fixtures.

Every test runs fully offline: partner APIs are disabled, the cache is a
throwaway ``tmp_path`` and no network request is allowed to leak through. Tests
that genuinely need the (large, pre-downloaded) Skyfield ephemeris opt in with
the :func:`repo_ephemeris` fixture.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_CACHE = Path(__file__).resolve().parent.parent / ".cache"


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    """Point every test at a throwaway cache dir and disable partner APIs."""
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    for var in (
        "OPENROUTER_API_KEY",
        "GOOGLE_API_KEY",
        "HF_API_KEY",
        "ELEVENLABS_API_KEY",
        "SERPAPI_API_KEY",
        "MONGODB_URI",
        "SENTRY_DSN",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "none")

    # Settings are cached; clear so env changes take effect.
    from horizon.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def repo_ephemeris(_isolated_cache, monkeypatch):
    """Point the sky engine at the repo's cached ephemeris.

    The autouse fixture redirects ``CACHE_DIR`` to a temp dir; reusing the repo
    ``.cache/de421.bsp`` keeps ephemeris-dependent tests fast. If it isn't
    present yet we try one download (as CI does); offline and cached-less, the
    dependent tests skip instead of failing.
    """
    monkeypatch.setenv("CACHE_DIR", str(REPO_CACHE))
    from horizon.config import get_settings

    get_settings.cache_clear()

    if not (REPO_CACHE / "de421.bsp").exists():  # pragma: no cover - CI / fresh clone
        REPO_CACHE.mkdir(parents=True, exist_ok=True)
        try:
            from horizon.sky import _load_ephemeris

            _load_ephemeris()
        except Exception:
            pytest.skip("de421.bsp unavailable and could not be downloaded")


@pytest.fixture
def sample_alert():
    """A representative, fully-populated :class:`DailyAlert` for the tests."""
    from horizon.models import (
        DailyAlert,
        HourlyPoint,
        Location,
        ProviderStatus,
        SkyReport,
        WeatherWindow,
    )

    window = WeatherWindow(
        start=datetime(2026, 10, 10, 17, 0, tzinfo=timezone.utc),
        end=datetime(2026, 10, 10, 19, 0, tzinfo=timezone.utc),
        hours=2,
        score=87.0,
        summary="clear sky",
        temperature_c=24.0,
        feels_like_c=24.5,
        precipitation_probability=5,
        wind_kph=8.0,
        cloud_cover=10,
        uv_index=2.0,
    )
    hourly = [
        HourlyPoint(
            time=datetime(2026, 10, 10, h, 0, tzinfo=timezone.utc),
            score=70.0 + h,
            temperature_c=20.0 + h / 10,
            precipitation_probability=5,
            cloud_cover=10,
            is_best=17 <= h < 19,
        )
        for h in range(24)
    ]
    return DailyAlert(
        location=Location(
            name="Test",
            latitude=17.385,
            longitude=78.4867,
            country="India",
            timezone="Asia/Kolkata",
            display_name="Test, India",
        ),
        generated_at=datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc),
        generated_for_date="2026-10-10",
        headline="Your best outside window is 17:00-19:00",
        message="Best window: 17:00-19:00 (clear sky, 24°C, 5% rain chance, score 87/100).",
        nudge="Put the phone in your pocket at 17:00 and go outside.",
        weather_summary="Clear sky, 24°C, wind 8 km/h.",
        best_window=window,
        hourly=hourly,
        sky_report=SkyReport(
            moon_phase_name="Waxing Crescent", moon_illumination=0.24, moon_age_days=7.1
        ),
        providers=ProviderStatus(),
    )
