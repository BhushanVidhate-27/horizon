"""Sky event engine built on Skyfield.

Computes, for a location and date:
  * sunrise / sunset / solar noon / civil twilight
  * moon phase, illumination, moonrise / moonset
  * which bright planets are up and reasonably placed
  * notable constellations currently high in the sky
  * major meteor showers near their peak

Skyfield downloads a small planetary ephemeris (``de421.bsp``) on first use.
If Skyfield or the ephemeris is unavailable the module degrades gracefully and
returns whatever it can, so the app still runs end-to-end.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .models import (
    Constellation,
    Location,
    MeteorShower,
    Planet,
    SkyEvent,
    SkyReport,
)

log = logging.getLogger("horizon.sky")

try:  # Skyfield is optional at import time so the API always boots.
    from skyfield import almanac
    from skyfield.api import Loader, Star, load, wgs84

    SKYFIELD_AVAILABLE = True
except Exception:  # pragma: no cover - import guard
    SKYFIELD_AVAILABLE = False
    log.warning("Skyfield not available; sky calculations will be limited.")

# --- Reference data ------------------------------------------------------

# Bright stars: (constellation, star, RA hours, Dec degrees, magnitude).
BRIGHT_STARS: list[tuple[str, str, float, float, float]] = [
    ("Canis Major", "Sirius", 6.7525, -16.716, -1.46),
    ("Canis Minor", "Procyon", 7.655, 5.225, 0.34),
    ("Boötes", "Arcturus", 14.261, 19.182, -0.05),
    ("Lyra", "Vega", 18.615, 38.784, 0.03),
    ("Auriga", "Capella", 5.278, 45.998, 0.08),
    ("Orion", "Rigel", 5.242, -8.202, 0.13),
    ("Orion", "Betelgeuse", 5.919, 7.407, 0.50),
    ("Taurus", "Aldebaran", 4.599, 16.509, 0.85),
    ("Aquila", "Altair", 19.846, 8.868, 0.77),
    ("Scorpius", "Antares", 16.490, -26.432, 0.96),
    ("Virgo", "Spica", 13.420, -11.161, 0.98),
    ("Gemini", "Pollux", 7.755, 28.026, 1.14),
    ("Cygnus", "Deneb", 20.690, 45.280, 1.25),
    ("Leo", "Regulus", 10.140, 11.967, 1.35),
    ("Ursa Major", "Dubhe", 11.062, 61.751, 1.79),
    ("Ursa Minor", "Polaris", 2.530, 89.264, 1.98),
    ("Cassiopeia", "Schedar", 0.675, 56.537, 2.24),
    ("Pegasus", "Markab", 23.079, 15.205, 2.49),
    ("Andromeda", "Alpheratz", 0.140, 29.090, 2.06),
    ("Perseus", "Mirfak", 3.405, 49.861, 1.79),
    ("Sagittarius", "Kaus Australis", 18.403, -34.385, 1.85),
    ("Crux", "Acrux", 12.443, -63.099, 0.77),
]

# Nominal apparent magnitudes; good enough for "is it an easy naked-eye object".
PLANET_MAGNITUDES = {
    "Mercury": -0.4,
    "Venus": -4.2,
    "Mars": 0.7,
    "Jupiter": -2.3,
    "Saturn": 0.6,
}

MOON_PHASES = [
    (22.5, "New Moon"),
    (67.5, "Waxing Crescent"),
    (112.5, "First Quarter"),
    (157.5, "Waxing Gibbous"),
    (202.5, "Full Moon"),
    (247.5, "Waning Gibbous"),
    (292.5, "Last Quarter"),
    (337.5, "Waning Crescent"),
    (360.1, "New Moon"),
]

_DIRECTIONS = [
    "N",
    "NNE",
    "NE",
    "ENE",
    "E",
    "ESE",
    "SE",
    "SSE",
    "S",
    "SSW",
    "SW",
    "WSW",
    "W",
    "WNW",
    "NW",
    "NNW",
]


def _direction(azimuth_deg: float) -> str:
    idx = int((azimuth_deg + 11.25) // 22.5) % 16
    return _DIRECTIONS[idx]


def _moon_phase_name(angle_deg: float) -> str:
    for threshold, name in MOON_PHASES:
        if angle_deg < threshold:
            return name
    return "New Moon"


def _load_ephemeris():
    """Load the DE421 ephemeris, downloading it once into the cache dir."""
    from .config import get_settings

    cache = Path(get_settings().cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    loader = Loader(str(cache))
    return loader("de421.bsp")


def _meteor_showers_for(date: datetime) -> list[MeteorShower]:
    path = Path(__file__).parent / "data" / "meteor_showers.json"
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):  # pragma: no cover - defensive
        return []

    showers: list[tuple[int, MeteorShower]] = []
    for item in raw:
        try:
            peak_month, peak_day = (int(x) for x in item["peak"].split("-"))
        except (KeyError, ValueError):
            continue

        # Distance to the *nearest* peak, checking the adjacent years too so a
        # shower just after New Year still finds the late-December occurrence.
        nearest_delta: int | None = None
        nearest_peak = None
        for year in (date.year - 1, date.year, date.year + 1):
            try:
                candidate = date.replace(
                    year=year,
                    month=peak_month,
                    day=peak_day,
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
            except ValueError:  # pragma: no cover - invalid calendar date
                continue
            delta = abs((date - candidate).days)
            if nearest_delta is None or delta < nearest_delta:
                nearest_delta, nearest_peak = delta, candidate

        if nearest_delta is not None and nearest_delta <= 10:
            showers.append(
                (
                    nearest_delta,
                    MeteorShower(
                        name=item["name"],
                        peak=nearest_peak.strftime("%b %d"),
                        active=item["active"],
                        zhr=int(item["zhr"]),
                        radiant=item["radiant"],
                        description=item["description"],
                        near_peak=nearest_delta <= 3,
                    ),
                )
            )
    # Nearer peaks first.
    showers.sort(key=lambda pair: pair[0])
    return [shower for _, shower in showers]


def compute_sky_report(location: Location, date: datetime | None = None) -> SkyReport:
    """Compute the full sky report for a location on a given date."""
    tz_name = location.timezone or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:  # pragma: no cover
        tz = ZoneInfo("UTC")
    date = (date or datetime.now(tz)).astimezone(tz)

    report = SkyReport()

    if not SKYFIELD_AVAILABLE:
        report.events.append(
            SkyEvent(
                kind="moon",
                label="Sky engine unavailable",
                detail="Install Skyfield to unlock sunrise, moon and planet details.",
            )
        )
        report.meteor_showers = _meteor_showers_for(date)
        return report

    try:
        eph = _load_ephemeris()
        ts = load.timescale()
        observer = eph["earth"] + wgs84.latlon(location.latitude, location.longitude)

        midnight = date.replace(hour=0, minute=0, second=0, microsecond=0)
        t0 = ts.from_datetime(midnight.astimezone(timezone.utc))
        t1 = ts.from_datetime((midnight + timedelta(days=1)).astimezone(timezone.utc))

        # --- Sun: rise / set / noon / twilight ---------------------------
        f_sun = almanac.sunrise_sunset(eph, wgs84.latlon(location.latitude, location.longitude))
        t_sun, y_sun = almanac.find_discrete(t0, t1, f_sun)
        for t, y in zip(t_sun, y_sun, strict=True):
            dt = t.astimezone(tz)
            if int(y) == 1:
                report.sunrise = dt
            else:
                report.sunset = dt

        f_twilight = almanac.dark_twilight_day(
            eph, wgs84.latlon(location.latitude, location.longitude)
        )
        t_tw, y_tw = almanac.find_discrete(t0, t1, f_twilight)
        # y==1 => civil twilight ends (sun at -6 deg) going into nautical dark.
        for t, y in zip(t_tw, y_tw, strict=True):
            if int(y) == 1:
                report.civil_twilight_end = t.astimezone(tz)
                break

        try:
            report.solar_noon = almanac.noon(
                eph, wgs84.latlon(location.latitude, location.longitude), t0, t1
            )[0].astimezone(tz)
        except Exception:  # pragma: no cover - almanac API drift
            report.solar_noon = None

        # --- Moon --------------------------------------------------------
        t_now = ts.from_datetime(datetime.now(timezone.utc))
        phase_angle = float(almanac.moon_phase(eph, t_now).degrees)
        report.moon_phase_name = _moon_phase_name(phase_angle)
        report.moon_illumination = round((1.0 - math.cos(math.radians(phase_angle))) / 2.0, 3)
        report.moon_age_days = round(phase_angle / 360.0 * 29.53, 1)

        f_moon = almanac.risings_and_settings(
            eph, eph["moon"], wgs84.latlon(location.latitude, location.longitude)
        )
        t_moon, y_moon = almanac.find_discrete(t0, t1, f_moon)
        for t, y in zip(t_moon, y_moon, strict=True):
            dt = t.astimezone(tz)
            if int(y) == 1:
                report.moonrise = dt
            else:
                report.moonset = dt

        # --- Planets -----------------------------------------------------
        sun_alt = observer.at(t_now).observe(eph["sun"]).apparent().altaz()[0].degrees
        report.planets = _planets(observer, eph, ts, t_now, sun_alt)

        # --- Constellations ---------------------------------------------
        report.constellations = _constellations(observer, ts, t_now)

        # --- Events / highlights ----------------------------------------
        report.events = _build_events(report)
    except Exception as exc:  # pragma: no cover - network/IO failures
        log.warning("Sky computation failed: %s", exc)
        report.events.append(SkyEvent(kind="moon", label="Sky data incomplete", detail=str(exc)))

    report.meteor_showers = _meteor_showers_for(date)
    return report


def _planets(observer, eph, ts, t_now, sun_alt: float) -> list[Planet]:
    planets: list[Planet] = []
    dark_enough = sun_alt < -6.0
    for name in ("Venus", "Jupiter", "Mars", "Saturn", "Mercury"):
        try:
            astrometric = observer.at(t_now).observe(eph[name.lower()])
            alt, az, _ = astrometric.apparent().altaz()
        except Exception:  # pragma: no cover
            continue
        magnitude = PLANET_MAGNITUDES.get(name)
        visible = alt.degrees > 5.0 and (
            dark_enough or (magnitude is not None and magnitude < -3.5)
        )
        planets.append(
            Planet(
                name=name,
                altitude_deg=round(alt.degrees, 1),
                azimuth_deg=round(az.degrees, 1),
                direction=_direction(az.degrees),
                magnitude=magnitude,
                visible=visible,
            )
        )
    planets.sort(key=lambda p: p.altitude_deg, reverse=True)
    return planets


def _constellations(observer, ts, t_now) -> list[Constellation]:
    found: dict[str, Constellation] = {}
    for constellation, star_name, ra_hours, dec_deg, _mag in BRIGHT_STARS:
        try:
            star = Star(ra_hours=ra_hours, dec_degrees=dec_deg)
            alt, az, _ = observer.at(t_now).observe(star).apparent().altaz()
        except Exception:  # pragma: no cover
            continue
        altitude = alt.degrees
        # Keep only star groups that are well placed and reasonably dark-ish.
        if altitude < 25.0:
            continue
        existing = found.get(constellation)
        if existing is None or altitude > existing.altitude_deg:
            found[constellation] = Constellation(
                name=constellation,
                star=star_name,
                altitude_deg=round(altitude, 1),
                direction=_direction(az.degrees),
            )
    return sorted(found.values(), key=lambda c: c.altitude_deg, reverse=True)[:5]


def _build_events(report: SkyReport) -> list[SkyEvent]:
    events: list[SkyEvent] = []

    if report.sunset:
        events.append(
            SkyEvent(
                kind="sun",
                label=f"Sunset at {report.sunset.strftime('%H:%M')}",
                detail="Golden hour starts just before sunset — great light for a walk.",
            )
        )

    events.append(
        SkyEvent(
            kind="moon",
            label=f"{report.moon_phase_name} ({int(report.moon_illumination * 100)}% lit)",
            detail=_moon_detail(report),
        )
    )

    visible = [p for p in report.planets if p.visible]
    for planet in visible[:2]:
        events.append(
            SkyEvent(
                kind="planet",
                label=f"{planet.name} {planet.direction} at {planet.altitude_deg:.0f}°",
                detail=f"Bright enough to spot with the naked eye in the {planet.direction} sky.",
            )
        )

    for constellation in report.constellations[:2]:
        events.append(
            SkyEvent(
                kind="constellation",
                label=f"{constellation.name} high overhead ({constellation.direction})",
                detail=f"Look for its bright star {constellation.star}.",
            )
        )

    for shower in [s for s in report.meteor_showers if s.near_peak][:1]:
        events.append(
            SkyEvent(
                kind="meteor",
                label=f"{shower.name} meteor shower near peak",
                detail=f"{shower.description} Look towards {shower.radiant}.",
            )
        )

    return events


def _moon_detail(report: SkyReport) -> str:
    bits = []
    if report.moonrise and report.moonset:
        bits.append(
            f"Rises {report.moonrise.strftime('%H:%M')}, sets {report.moonset.strftime('%H:%M')}."
        )
    elif report.moonrise:
        bits.append(f"Rises around {report.moonrise.strftime('%H:%M')}.")
    if report.moon_illumination < 0.25:
        bits.append("Dark skies — ideal for stargazing.")
    elif report.moon_illumination > 0.75:
        bits.append("Bright moon — memorable but washes out faint stars.")
    return " ".join(bits) or "Check the sky tonight."
