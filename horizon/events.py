"""Upcoming notable sky events — the engine behind the in-app calendar.

Highlights only what is worth planning around:

  * **Moon** — new / full moons (the quarters are returned too, but only as
    "minor" so the calendar stays uncluttered).
  * **Meteors** — shower peaks from :mod:`horizon.data.meteor_showers`.
  * **Seasons** — equinoxes and solstices.
  * **Planets** — oppositions, when an outer planet is at its biggest, brightest
    and closest.

Everything is computed with Skyfield (the same engine as the sky report) plus
the packed meteor-shower dataset. No API key, no network — the calendar loads
instantly. Each event carries an ``importance`` (1 minor → 3 major); the UI
highlights only 2+.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import CalendarEvent

log = logging.getLogger("horizon.events")

try:  # Skyfield is optional so the API always boots.
    from skyfield import almanac
    from skyfield.api import load

    SKYFIELD_AVAILABLE = True
except Exception:  # pragma: no cover - import guard
    SKYFIELD_AVAILABLE = False
    log.warning("Skyfield not available; the sky calendar will be limited.")

# almanac.moon_phases index -> (title, importance, detail)
MOON_PHASES = {
    0: ("New Moon", 2, "Darkest skies of the month — the best night for stargazing."),
    1: ("First Quarter Moon", 1, "Half-lit, high in the evening sky."),
    2: ("Full Moon", 2, "The brightest night of the month — lovely for a moonlit walk."),
    3: ("Last Quarter Moon", 1, "Half-lit, rising after midnight."),
}

# almanac.seasons index -> (title, importance, detail)
SEASONS = {
    0: ("March Equinox", 2, "Day and night are roughly equal length."),
    1: ("June Solstice", 2, "The longest day of the year in the northern hemisphere."),
    2: ("September Equinox", 2, "Day and night are roughly equal length."),
    3: ("December Solstice", 2, "The shortest day of the year in the northern hemisphere."),
}

# planet barycenter key -> display name
OUTER_PLANETS = {
    "JUPITER BARYCENTER": "Jupiter",
    "SATURN BARYCENTER": "Saturn",
    "MARS BARYCENTER": "Mars",
}


def _ephemeris():
    from .sky import _load_ephemeris

    return _load_ephemeris()


def _meteor_events(start: datetime, end: datetime) -> list[CalendarEvent]:
    path = Path(__file__).parent / "data" / "meteor_showers.json"
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):  # pragma: no cover - defensive
        return []

    events: list[CalendarEvent] = []
    for year in {start.year, end.year}:
        for item in raw:
            try:
                month, day = (int(x) for x in item["peak"].split("-"))
                peak = datetime(year, month, day, tzinfo=timezone.utc)
            except (ValueError, KeyError):
                continue
            if not (start <= peak <= end):
                continue
            zhr = int(item["zhr"])
            importance = 3 if zhr >= 50 else 2 if zhr >= 20 else 1
            events.append(
                CalendarEvent(
                    date=peak.date().isoformat(),
                    title=f"{item['name']} meteor shower peaks",
                    kind="meteor",
                    importance=importance,
                    detail=(
                        f"Up to ~{zhr} meteors/hour at the peak. "
                        f"{item.get('description', '')} Look towards {item.get('radiant', 'the sky')}."
                    ).strip(),
                )
            )
    return events


def _moon_events(eph, t0, t1) -> list[CalendarEvent]:
    t, y = almanac.find_discrete(t0, t1, almanac.moon_phases(eph))
    events: list[CalendarEvent] = []
    for i in range(len(t)):
        title, importance, detail = MOON_PHASES[int(y[i])]
        events.append(
            CalendarEvent(
                date=t[i].utc_strftime("%Y-%m-%d"),
                title=title,
                kind="moon",
                importance=importance,
                detail=detail,
                time=t[i].utc_strftime("%H:%M"),
            )
        )
    return events


def _season_events(eph, t0, t1) -> list[CalendarEvent]:
    t, y = almanac.find_discrete(t0, t1, almanac.seasons(eph))
    events: list[CalendarEvent] = []
    for i in range(len(t)):
        title, importance, detail = SEASONS[int(y[i])]
        events.append(
            CalendarEvent(
                date=t[i].utc_strftime("%Y-%m-%d"),
                title=title,
                kind="season",
                importance=importance,
                detail=detail,
                time=t[i].utc_strftime("%H:%M"),
            )
        )
    return events


def _planet_events(eph, t0, t1) -> list[CalendarEvent]:
    events: list[CalendarEvent] = []
    for key, label in OUTER_PLANETS.items():
        try:
            target = eph[key]
            t, y = almanac.find_discrete(t0, t1, almanac.oppositions_conjunctions(eph, target))
        except Exception as exc:
            log.debug("Skipping %s opposition lookup: %s", label, exc)
            continue
        for i in range(len(t)):
            if int(y[i]) != 1:  # 1 == opposition
                continue
            events.append(
                CalendarEvent(
                    date=t[i].utc_strftime("%Y-%m-%d"),
                    title=f"{label} at opposition",
                    kind="planet",
                    importance=3,
                    detail=(
                        f"{label} is at its biggest and brightest, rising as the Sun sets "
                        "and visible all night."
                    ),
                    time=t[i].utc_strftime("%H:%M"),
                )
            )
    return events


def upcoming_events(days: int = 90, start: datetime | None = None) -> list[CalendarEvent]:
    """Return every notable sky event in the next ``days`` days, sorted by date.

    Events are global (moon phases and oppositions happen for everyone), so the
    calendar needs no location and stays fast.
    """
    start = (start or datetime.now(timezone.utc)).astimezone(timezone.utc)
    end = start + timedelta(days=max(1, days))

    events = _meteor_events(start, end)

    if SKYFIELD_AVAILABLE:
        try:
            eph = _ephemeris()
            ts = load.timescale()
            t0 = ts.from_datetime(start)
            t1 = ts.from_datetime(end)
            events += _moon_events(eph, t0, t1)
            events += _season_events(eph, t0, t1)
            events += _planet_events(eph, t0, t1)
        except Exception as exc:
            log.warning("Sky calendar computation failed: %s", exc)

    events.sort(key=lambda e: (e.date, -e.importance, e.title))
    return events
