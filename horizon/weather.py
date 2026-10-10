"""Weather scoring via Open-Meteo.

Fetches an hourly forecast and scores every hour for how nice it is to be
outside. The score blends what makes going outside *pleasant* (temperature, low
rain chance, gentle wind, manageable UV) with what makes the *sky* worth looking
at (clear cloud cover). It is intentionally explainable so the daily alert can
say *why* a window won.

A single fetch powers both:
  * :func:`get_weather` -> the best 1-3h window **and** the hourly score series
    used by the UI's hourly strip.
  * :func:`get_best_window` -> the window alone (thin wrapper, kept for tests).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from .config import get_settings
from .models import HourlyPoint, Location, WeatherWindow

log = logging.getLogger("horizon.weather")

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

HOURLY_FIELDS = [
    "temperature_2m",
    "apparent_temperature",
    "precipitation_probability",
    "precipitation",
    "wind_speed_10m",
    "cloud_cover",
    "uv_index",
    "weather_code",
]

WMO_CODES = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "drizzle",
    55: "dense drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    80: "light showers",
    81: "showers",
    82: "violent showers",
    95: "thunderstorm",
    96: "thunderstorm with hail",
    99: "severe thunderstorm with hail",
}

# WMO code -> UI icon key (see static/app.js).
WMO_ICONS = {
    0: "sun",
    1: "mostly-clear",
    2: "partly-cloudy",
    3: "cloud",
    45: "fog",
    48: "fog",
    51: "drizzle",
    53: "drizzle",
    55: "drizzle",
    61: "rain",
    63: "rain",
    65: "rain",
    71: "snow",
    73: "snow",
    75: "snow",
    80: "rain",
    81: "rain",
    82: "rain",
    95: "storm",
    96: "storm",
    99: "storm",
}


def _comfort_temperature(temp_c: float) -> float:
    """0-1 sub-score peaking around 18 °C, tolerant of mild deviations."""
    ideal = 18.0
    return max(0.0, 1.0 - (abs(temp_c - ideal) / 22.0))


def _score_hour(hour: dict) -> float:
    """Score a single hour from 0-100."""
    temp = float(hour["temperature_2m"])
    precip_prob = float(hour.get("precipitation_probability") or 0)
    precip = float(hour.get("precipitation") or 0)
    wind = float(hour.get("wind_speed_10m") or 0)
    cloud = float(hour.get("cloud_cover") or 0)
    uv = float(hour.get("uv_index") or 0)

    score = 0.0
    score += 34.0 * _comfort_temperature(temp)
    score += 22.0 * (1.0 - min(precip_prob, 100.0) / 100.0)
    score += 10.0 * (1.0 - min(precip, 5.0) / 5.0)
    score += 12.0 * (1.0 - min(wind, 45.0) / 45.0)
    # Clear skies score highest: this is a "look up" app, not just a comfort one.
    score += 12.0 * (1.0 - min(cloud, 100.0) / 100.0)
    score += 10.0 * (1.0 - min(uv, 11.0) / 11.0)

    return round(max(0.0, min(score, 100.0)), 1)


def _describe(hour: dict) -> str:
    code = int(hour.get("weather_code") or 0)
    return WMO_CODES.get(code, "mixed conditions")


def _icon_for(hour: dict) -> str:
    code = int(hour.get("weather_code") or 0)
    return WMO_ICONS.get(code, "cloud")


def _fetch_hourly(location: Location) -> tuple[ZoneInfo, list[dict]]:
    """Fetch and normalize the hourly forecast for a location."""
    settings = get_settings()
    params = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "hourly": ",".join(HOURLY_FIELDS),
        "current": "temperature_2m,weather_code,wind_speed_10m,cloud_cover",
        "timezone": "auto",
        "forecast_days": 2,
    }

    try:
        resp = httpx.get(FORECAST_URL, params=params, timeout=settings.request_timeout)
        resp.raise_for_status()
        payload = resp.json()
    except httpx.HTTPError as exc:
        log.warning("Weather fetch failed: %s", exc)
        return ZoneInfo("UTC"), []

    try:
        tz = ZoneInfo(payload.get("timezone") or "UTC")
    except Exception:  # pragma: no cover - unknown tz name
        tz = ZoneInfo("UTC")

    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    rows: list[dict] = []
    for i, iso in enumerate(times):
        try:
            dt = datetime.fromisoformat(iso).replace(tzinfo=tz)
        except ValueError:  # pragma: no cover - defensive
            continue
        row = {"dt": dt}
        for field in HOURLY_FIELDS:
            values = hourly.get(field) or []
            row[field] = values[i] if i < len(values) else None
        rows.append(row)
    return tz, rows


def _daylight_bonus(
    dt: datetime, daylight: tuple[datetime | None, datetime | None] | None
) -> float:
    if not daylight:
        return 0.0
    sunrise, sunset = daylight
    if sunrise and sunset and (sunrise - timedelta(hours=1)) <= dt <= (sunset + timedelta(hours=1)):
        return 8.0
    return 0.0


def _best_window(
    future: list[dict],
    daylight: tuple[datetime | None, datetime | None] | None,
) -> WeatherWindow | None:
    best: tuple[float, int, int] | None = None  # (adjusted_score, start_idx, length)
    for length in (3, 2, 1):
        for start in range(max(0, len(future) - length + 1)):
            block = future[start : start + length]
            avg = (
                sum(min(100.0, _score_hour(r) + _daylight_bonus(r["dt"], daylight)) for r in block)
                / length
            )
            adjusted = avg + length * 0.5  # prefer longer, contiguous windows
            if best is None or adjusted > best[0]:
                best = (adjusted, start, length)

    if best is None:
        return None

    _, start, length = best
    block = future[start : start + length]
    avg_score = round(
        sum(min(100.0, _score_hour(r) + _daylight_bonus(r["dt"], daylight)) for r in block)
        / length,
        1,
    )
    first, last = block[0], block[-1]
    return WeatherWindow(
        start=first["dt"],
        end=last["dt"] + timedelta(hours=1),
        hours=length,
        score=avg_score,
        summary=_describe(first),
        temperature_c=round(float(first["temperature_2m"]), 1),
        feels_like_c=round(float(first.get("apparent_temperature") or first["temperature_2m"]), 1),
        precipitation_probability=int(first.get("precipitation_probability") or 0),
        wind_kph=round(float(first.get("wind_speed_10m") or 0), 1),
        cloud_cover=int(first.get("cloud_cover") or 0),
        uv_index=round(float(first.get("uv_index") or 0), 1),
    )


def _hourly_points(
    future: list[dict],
    now: datetime,
    window: WeatherWindow | None,
    daylight: tuple[datetime | None, datetime | None] | None,
    limit: int = 24,
) -> list[HourlyPoint]:
    start = now.replace(minute=0, second=0, microsecond=0)
    points: list[HourlyPoint] = []
    for row in future:
        if row["dt"] < start:
            continue
        if len(points) >= limit:
            break
        is_best = bool(window and window.start <= row["dt"] < window.end)
        points.append(
            HourlyPoint(
                time=row["dt"],
                score=round(min(100.0, _score_hour(row) + _daylight_bonus(row["dt"], daylight)), 1),
                temperature_c=round(float(row["temperature_2m"]), 1),
                feels_like_c=round(
                    float(row.get("apparent_temperature") or row["temperature_2m"]), 1
                ),
                precipitation_probability=int(row.get("precipitation_probability") or 0),
                wind_kph=round(float(row.get("wind_speed_10m") or 0), 1),
                cloud_cover=int(row.get("cloud_cover") or 0),
                uv_index=round(float(row.get("uv_index") or 0), 1),
                icon=_icon_for(row),
                is_best=is_best,
            )
        )
    return points


def get_weather(
    location: Location,
    now: datetime | None = None,
    daylight: tuple[datetime | None, datetime | None] | None = None,
) -> tuple[WeatherWindow | None, list[HourlyPoint]]:
    """Return ``(best_window, hourly_points)`` from a single forecast fetch."""
    tz, rows = _fetch_hourly(location)
    if not rows:
        return None, []

    now = (now or datetime.now(tz)).astimezone(tz)
    future = [r for r in rows if r["dt"] >= now - timedelta(hours=1)] or rows

    window = _best_window(future, daylight)
    points = _hourly_points(future, now, window, daylight)
    return window, points


def get_best_window(
    location: Location,
    now: datetime | None = None,
    daylight: tuple[datetime | None, datetime | None] | None = None,
) -> WeatherWindow | None:
    """Return just the best contiguous 1-3 hour window (thin wrapper)."""
    return get_weather(location, now=now, daylight=daylight)[0]
