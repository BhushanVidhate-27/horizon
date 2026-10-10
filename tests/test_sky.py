"""Sky engine tests (offline; do not require the ephemeris download)."""

from datetime import datetime

from horizon import sky
from horizon.models import Location

LOC = Location(name="Test", latitude=17.385, longitude=78.4867, timezone="Asia/Kolkata")


def test_moon_phase_names():
    assert sky._moon_phase_name(0) == "New Moon"
    assert sky._moon_phase_name(180) == "Full Moon"
    assert sky._moon_phase_name(90) == "First Quarter"
    assert sky._moon_phase_name(270) == "Last Quarter"


def test_direction_mapping():
    assert sky._direction(0) == "N"
    assert sky._direction(90) == "E"
    assert sky._direction(180) == "S"
    assert sky._direction(270) == "W"


def test_meteor_showers_near_orionids_peak():
    # Oct 21 is the Orionids peak.
    showers = sky._meteor_showers_for(datetime(2026, 10, 20, 22, 0))
    names = {s.name for s in showers}
    assert "Orionids" in names
    orionids = next(s for s in showers if s.name == "Orionids")
    assert orionids.near_peak is True


def test_no_showers_in_quiet_window():
    # Early September is between the major peaks.
    showers = sky._meteor_showers_for(datetime(2026, 9, 1, 22, 0))
    assert all(not s.near_peak for s in showers)


def test_meteor_shower_year_wrap():
    """A shower peaking in early January must be found from late December."""
    showers = sky._meteor_showers_for(datetime(2026, 12, 31, 22, 0))
    quadrantids = next((s for s in showers if s.name == "Quadrantids"), None)
    assert quadrantids is not None
    assert quadrantids.near_peak is True


def test_compute_sky_report_offline(repo_ephemeris):
    """Full Skyfield run against the cached ephemeris (no network)."""
    report = sky.compute_sky_report(LOC, datetime(2026, 10, 10, 20, 0))

    assert report.sunrise is not None and report.sunset is not None
    assert report.sunrise < report.sunset
    assert report.moon_phase_name in {name for _, name in sky.MOON_PHASES}
    assert 0.0 <= report.moon_illumination <= 1.0
    assert report.planets  # always the five bright planets, visible or not
    assert report.events
