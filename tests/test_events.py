"""Tests for the sky-event calendar (the app's planning view)."""

from datetime import datetime, timezone

import pytest

from horizon.events import upcoming_events


@pytest.fixture
def events(repo_ephemeris):
    # A 100-day window includes at least two new moons, a full moon, meteor
    # peaks and a solstice — enough to exercise every event type.
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    return upcoming_events(days=100, start=start)


def test_events_are_sorted(events):
    dates = [e.date for e in events]
    assert dates == sorted(dates)
    assert len(events) >= 10


def test_has_major_and_notable_and_minor(events):
    importance = {e.importance for e in events}
    assert importance & {2, 3}, "calendar should highlight notable+ events"
    assert 1 in importance, "minor events still inform the planner"


def test_new_and_full_moon_present(events):
    titles = {e.title for e in events}
    assert "New Moon" in titles
    assert "Full Moon" in titles


def test_meteor_peaks_are_unique_per_date(events):
    seen = set()
    for e in events:
        if e.kind != "meteor":
            continue
        key = (e.date, e.title)
        assert key not in seen, f"duplicate meteor event {key}"
        seen.add(key)


def test_midwinter_has_december_solstice(events):
    dec = [e for e in events if e.title == "December Solstice"]
    assert dec and dec[0].date >= "2026-12-20"


def test_events_endpoint_via_app(repo_ephemeris):
    from fastapi.testclient import TestClient

    from horizon.main import app

    client = TestClient(app)
    res = client.get("/api/events?days=60")
    assert res.status_code == 200
    payload = res.json()
    assert payload["events"] and payload["events"][0]["importance"] >= 1


def test_events_endpoint_bounds(repo_ephemeris):
    from fastapi.testclient import TestClient

    from horizon.main import app

    client = TestClient(app)
    assert client.get("/api/events?days=3").status_code == 422  # below minimum
    assert client.get("/api/events?days=700").status_code == 422  # above maximum
