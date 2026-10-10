"""Geocoding tests (offline; HTTP is monkeypatched)."""

import httpx

from horizon import geocode


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _router(routes):
    """Build a fake ``httpx.get`` that answers by URL fragment."""

    def fake_get(url, params=None, timeout=None, headers=None, **kwargs):
        for fragment, payload in routes.items():
            if fragment in url:
                return _FakeResponse(payload)
        raise httpx.ConnectError(f"no route for {url}")

    return fake_get


def test_geocode_caches_results(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, params=None, timeout=None, headers=None, **kwargs):
        calls["n"] += 1
        return _FakeResponse(
            {
                "results": [
                    {
                        "name": "Lisbon",
                        "latitude": 38.7167,
                        "longitude": -9.1333,
                        "country": "Portugal",
                        "feature_code": "PPLC",
                        "timezone": "Europe/Lisbon",
                    }
                ]
            }
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    first = geocode.geocode_city("Lisbon")
    second = geocode.geocode_city("Lisbon")

    assert first is not None and first.latitude == 38.7167
    assert first.display_name == "Lisbon, Portugal"
    assert second is not None and second.name == "Lisbon"
    assert calls["n"] == 1  # second call served from cache


def test_geocode_unknown_city_returns_none(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResponse({"results": []}))
    assert geocode.geocode_city("Nowhereville") is None


def test_geocode_prefers_exact_village_over_larger_partial_match(monkeypatch):
    """An exact-name village must beat a big city that merely contains the query."""
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *a, **k: _FakeResponse(
            {
                "results": [
                    {
                        "name": "Kothaguda Junction",
                        "latitude": 1.0,
                        "longitude": 1.0,
                        "population": 5_000_000,
                        "feature_code": "PPL",
                    },
                    {
                        "name": "Kothaguda",
                        "latitude": 17.459,
                        "longitude": 78.365,
                        "population": 900,
                        "feature_code": "PPL",
                        "admin1": "Telangana",
                        "admin2": "Ranga Reddy",
                        "admin3": "Serilingampally",
                        "country": "India",
                        "timezone": "Asia/Kolkata",
                    },
                ]
            }
        ),
    )

    loc = geocode.geocode_city("Kothaguda")
    assert loc is not None and loc.name == "Kothaguda"
    assert loc.timezone == "Asia/Kolkata"
    assert loc.display_name == "Kothaguda, Serilingampally, Ranga Reddy, Telangana, India"


def test_resolve_location_falls_back_to_coordinates(monkeypatch):
    """When reverse geocoding is unavailable, coordinates are used as a label."""
    monkeypatch.setattr(
        httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("offline"))
    )

    loc = geocode.resolve_location(latitude=48.85, longitude=2.35)
    assert loc.latitude == 48.85
    assert loc.source == "coordinates"
    assert loc.name == "48.850, 2.350"


def test_reverse_geocode_resolves_village_name(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "get",
        _router(
            {
                "nominatim": {
                    "address": {
                        "village": "Kondapur",
                        "county": "Serilingampalle mandal",
                        "state_district": "Ranga Reddy",
                        "state": "Telangana",
                        "postcode": "500084",
                        "country": "India",
                        "country_code": "in",
                    }
                },
                "bigdatacloud": {
                    "city": "Hyderabad",
                    "locality": "Kondapur",
                    "countryName": "India",
                    "countryCode": "IN",
                    "principalSubdivision": "Telangana",
                    "localityInfo": {
                        "informative": [{"name": "Asia/Kolkata", "description": "time zone"}]
                    },
                },
                "open-meteo.com/v1/forecast": {"timezone": "Asia/Kolkata", "elevation": 542},
            }
        ),
    )

    loc = geocode.reverse_geocode(17.459, 78.365)
    assert loc is not None
    assert loc.name == "Kondapur"
    assert loc.source == "reverse"
    assert loc.timezone == "Asia/Kolkata"
    assert loc.elevation == 542
    assert loc.admin1 == "Telangana"
    assert loc.admin2 == "Ranga Reddy"
    assert "Kondapur" in loc.display_name
    assert "India" in loc.display_name


def test_clean_local_strips_noise_prefix():
    assert geocode._clean_local("Ward 104 Kondapur") == "Kondapur"
    assert geocode._clean_local("  ") is None
    assert geocode._clean_local(None) is None


def test_score_hit_prefers_exact_name_over_population():
    exact = {"name": "Bristol", "population": 500_000, "feature_code": "PPL"}
    partial = {"name": "Bristol City", "population": 9_000_000, "feature_code": "PPL"}
    assert geocode._score_hit("Bristol", exact) > geocode._score_hit("Bristol", partial)


def test_compose_display_name_deduplicates():
    from horizon.models import Location

    loc = Location(
        name="Pune",
        latitude=1,
        longitude=2,
        admin1="Maharashtra",
        admin2="Pune",
        country="India",
    )
    assert geocode._compose_display_name(loc) == "Pune, Maharashtra, India"


def test_resolve_location_unknown_city_falls_back_to_default(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResponse({"results": []}))
    loc = geocode.resolve_location(city="Nowhereville")
    assert loc.source == "default"
    assert loc.name


def test_resolve_location_without_reverse_geocoding(monkeypatch):
    monkeypatch.setenv("REVERSE_GEOCODE_ENABLED", "false")
    from horizon.config import get_settings

    get_settings.cache_clear()

    def boom(*args, **kwargs):  # pragma: no cover - should not be called
        raise AssertionError("reverse geocoding should be disabled")

    monkeypatch.setattr(httpx, "get", boom)
    loc = geocode.resolve_location(latitude=48.85, longitude=2.35)
    assert loc.source == "coordinates"
    assert loc.name == "48.850, 2.350"


def test_reverse_geocode_falls_back_to_bigdatacloud(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "get",
        _router(
            {
                "nominatim": {},  # no address -> Nominatim yields nothing
                "bigdatacloud": {
                    "city": "Hyderabad",
                    "locality": "Kondapur",
                    "countryName": "India",
                    "countryCode": "IN",
                    "principalSubdivision": "Telangana",
                    "localityInfo": {
                        "informative": [{"name": "Asia/Kolkata", "description": "time zone"}]
                    },
                },
                "open-meteo.com/v1/forecast": {"timezone": "Asia/Kolkata", "elevation": 542},
            }
        ),
    )
    loc = geocode.reverse_geocode(17.459, 78.365)
    assert loc is not None
    assert loc.name == "Kondapur"
    assert loc.source == "reverse"


def test_geocode_http_error_returns_none(monkeypatch):
    def boom(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "get", boom)
    assert geocode.geocode_city("Lisbon") is None
