"""Storage layer: SQLite fallback round-trips (offline)."""

from horizon.storage import Storage


def test_starts_empty_on_sqlite():
    store = Storage()
    assert store.backend == "sqlite"
    assert store.stats() == {"backend": "sqlite", "alerts": 0, "locations": 0}


def test_alert_roundtrip_and_search(sample_alert):
    store = Storage()
    store.save_alert(sample_alert)

    recent = store.recent_alerts()
    assert len(recent) == 1
    assert recent[0]["headline"] == sample_alert.headline
    assert recent[0]["location"]["name"] == "Test"

    # Location-filtered history.
    assert store.recent_alerts(location_name="Test")
    assert store.recent_alerts(location_name="Elsewhere") == []

    # Full-text-ish search over the stored payload.
    assert store.search_history("best window") or store.search_history("Best window")
    assert store.search_history("no-such-string") == []

    assert store.stats()["alerts"] == 1


def test_limit_is_respected(sample_alert):
    store = Storage()
    for _ in range(3):
        store.save_alert(sample_alert)
    assert len(store.recent_alerts(limit=2)) == 2


def test_location_preferences_upsert(sample_alert):
    store = Storage()
    assert store.get_location_pref("Test") is None

    store.save_location_pref("Test", sample_alert.location)
    got = store.get_location_pref("Test")
    assert got is not None and got.name == "Test"

    # Saving again updates in place rather than duplicating.
    moved = sample_alert.location.model_copy(update={"name": "Moved"})
    store.save_location_pref("Test", moved)
    assert store.get_location_pref("Test").name == "Moved"
    assert store.stats()["locations"] == 1
