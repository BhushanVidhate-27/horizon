"""Weather scoring tests (fully offline)."""

from datetime import datetime, timezone

import httpx

from horizon.models import Location
from horizon.weather import (
    _comfort_temperature,
    _describe,
    _icon_for,
    _score_hour,
    get_best_window,
    get_weather,
)


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _clear_payload():
    times = [f"2026-10-10T{h:02d}:00" for h in range(24)]

    def col(v):
        return [v] * 24

    return {
        "timezone": "UTC",
        "hourly": {
            "time": times,
            "temperature_2m": col(20),
            "apparent_temperature": col(20),
            "precipitation_probability": col(0),
            "precipitation": col(0),
            "wind_speed_10m": col(5),
            "cloud_cover": col(0),
            "uv_index": col(3),
            "weather_code": col(0),
        },
    }


def _hour(temp=20, precip_prob=0, precip=0, wind=5, cloud=0, uv=3, code=0):
    return {
        "temperature_2m": temp,
        "precipitation_probability": precip_prob,
        "precipitation": precip,
        "wind_speed_10m": wind,
        "cloud_cover": cloud,
        "uv_index": uv,
        "weather_code": code,
    }


def test_comfort_peaks_near_18c():
    assert _comfort_temperature(18) == 1.0
    assert _comfort_temperature(0) < _comfort_temperature(18)
    assert _comfort_temperature(40) < _comfort_temperature(18)


def test_clear_mild_hour_scores_high():
    score = _score_hour(_hour())
    assert score > 80


def test_rainy_windy_hour_scores_low():
    score = _score_hour(_hour(temp=38, precip_prob=95, precip=4, wind=40, cloud=100, uv=10))
    assert score < 40


def test_score_is_bounded():
    assert 0 <= _score_hour(_hour(temp=-30, precip_prob=100, precip=5, wind=60, uv=12)) <= 100
    assert 0 <= _score_hour(_hour(temp=25)) <= 100


def test_best_window_prefers_daylight_when_conditions_allow(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResp(_clear_payload()))
    loc = Location(name="T", latitude=0.0, longitude=0.0, timezone="UTC")
    now = datetime(2026, 10, 10, 0, 0, tzinfo=timezone.utc)

    dark = get_best_window(loc, now=now)
    day = get_best_window(
        loc,
        now=now,
        daylight=(
            datetime(2026, 10, 10, 6, tzinfo=timezone.utc),
            datetime(2026, 10, 10, 18, tzinfo=timezone.utc),
        ),
    )

    # Equal conditions all day -> without a daylight hint the first window wins.
    assert dark is not None and dark.start.hour == 0
    # With a daylight hint the recommendation shifts into the waking hours.
    assert day is not None and day.start.hour >= 5


def test_clear_skies_score_higher_than_overcast():
    """Regression: the cloud term must reward clear skies, not cloud cover."""
    assert _score_hour(_hour(cloud=0)) > _score_hour(_hour(cloud=100))


def test_describe_and_icon_mapping():
    assert _describe({"weather_code": 0}) == "clear sky"
    assert _describe({"weather_code": 999}) == "mixed conditions"
    assert _icon_for({"weather_code": 95}) == "storm"
    assert _icon_for({"weather_code": 999}) == "cloud"


def test_get_weather_returns_window_and_hourly_series(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResp(_clear_payload()))
    loc = Location(name="T", latitude=0.0, longitude=0.0, timezone="UTC")
    now = datetime(2026, 10, 10, 0, 0, tzinfo=timezone.utc)

    window, points = get_weather(loc, now=now)

    assert window is not None and window.hours in (1, 2, 3)
    assert 0 < len(points) <= 24
    assert any(p.is_best for p in points)
    assert all(0 <= p.score <= 100 for p in points)
    assert points[0].icon == "sun"


def test_get_weather_handles_fetch_failure(monkeypatch):
    def boom(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "get", boom)
    loc = Location(name="T", latitude=0.0, longitude=0.0, timezone="UTC")
    assert get_weather(loc) == (None, [])
