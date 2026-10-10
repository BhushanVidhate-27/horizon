"""Location resolution with an on-disk cache.

Turns a free-text place name (city, town **or village**) or bare lat/long into a
:class:`Location`. Everything here uses free, key-less services:

Forward search — **Open-Meteo geocoding** (backed by GeoNames)
    Resolves places down to village level (``feature_code`` ``PPL``) and returns
    the administrative hierarchy (state → district → mandal), elevation and
    timezone. We ask for several candidates and pick the best match instead of
    blindly trusting the first result.

Reverse search — **OpenStreetMap Nominatim**, enriched by **BigDataCloud**
    A GPS fix (e.g. from the browser) is turned into an *actual place name* —
    the village / suburb / neighbourhood — plus a full address. BigDataCloud
    adds the timezone and any missing administrative levels in a single call.
    This is what stops coordinates from showing up as "12.34, 56.78".

Every lookup is cached in ``.cache/geocode.json`` so repeat lookups are instant
and the app keeps working offline.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import httpx

from .config import get_settings
from .models import Location

log = logging.getLogger("horizon.geocode")

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
BIGDATACLOUD_URL = "https://api.bigdatacloud.net/data/reverse-geocode-client"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Nominatim's usage policy asks clients to identify themselves.
USER_AGENT = "Horizon/0.1 (Hacktoberfest 2026 daily outside alert; +https://github.com/)"

# Administrative names like "Ward 104 Kondapur" are noisy — keep the place name.
_NOISE_PREFIX = re.compile(r"^(ward|zone|sector|block)\s+\d+\s+", re.IGNORECASE)


# --- cache -----------------------------------------------------------------
def _cache_path() -> Path:
    settings = get_settings()
    path = Path(settings.cache_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path / "geocode.json"


def _load_cache() -> dict:
    path = _cache_path()
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):  # pragma: no cover - defensive
            log.warning("Could not read geocode cache at %s", path)
    return {}


def _save_cache(cache: dict) -> None:
    try:
        _cache_path().write_text(json.dumps(cache, indent=2))
    except OSError:  # pragma: no cover - defensive
        log.warning("Could not write geocode cache")


# --- helpers ---------------------------------------------------------------
def _clean_local(name: str | None) -> str | None:
    """Strip noisy prefixes like ``Ward 104 `` from a local place name."""
    if not name:
        return None
    cleaned = _NOISE_PREFIX.sub("", name).strip(" ,")
    return cleaned or None


def _compose_display_name(location: Location) -> str:
    """Build a tidy hierarchical label: place → district → state → country."""
    parts: list[str] = []
    for value in (
        location.name,
        location.admin4,
        location.admin3,
        location.admin2,
        location.admin1,
        location.country,
    ):
        value = (value or "").strip()
        if value and value not in parts:
            parts.append(value)
    return ", ".join(parts)


def _score_hit(query: str, hit: dict) -> float:
    """Rank a geocoding candidate against the user's query.

    Exact name matches win outright; a partial/contained match is worth far
    less. Populated places (``PPL*``) beat administrative regions, and — only
    as a small tie-breaker — larger populations edge out tiny ones, without
    ever being able to outweigh an exact-name match.
    """
    q = query.strip().lower()
    name = (hit.get("name") or "").lower()

    score = 0.0
    if name == q:
        score += 100.0
    elif q and (q in name or name in q):
        score += 35.0

    # Small tie-breaker only (max 4.0): never enough to outweigh an exact match.
    score += min(float(hit.get("population") or 0), 2_000_000) / 500_000.0

    code = (hit.get("feature_code") or "").upper()
    if code.startswith("PPL"):
        score += 6.0
    elif code.startswith("ADM"):
        score -= 4.0
    return score


def _location_from_geonames(hit: dict, fallback_name: str | None = None) -> Location:
    location = Location(
        name=hit.get("name") or fallback_name or "Unknown",
        latitude=float(hit["latitude"]),
        longitude=float(hit["longitude"]),
        country=hit.get("country"),
        country_code=(hit.get("country_code") or "").upper() or None,
        admin1=hit.get("admin1"),
        admin2=hit.get("admin2"),
        admin3=hit.get("admin3"),
        admin4=hit.get("admin4"),
        postcode=hit.get("postcode"),
        feature_code=hit.get("feature_code"),
        population=hit.get("population"),
        elevation=hit.get("elevation"),
        timezone=hit.get("timezone"),
        source="geocode",
    )
    location.display_name = _compose_display_name(location)
    return location


# --- forward geocoding -----------------------------------------------------
def geocode_city(name: str, limit: int = 10) -> Location | None:
    """Resolve a place name (city, town or village) to a Location.

    Requests several candidates and picks the best match so same-named villages
    and cities are disambiguated by exact-name scoring rather than luck.
    """
    key = name.strip().lower()
    if not key:
        return None

    cache = _load_cache()
    if key in cache:
        return Location(**cache[key])

    settings = get_settings()
    params = {"name": name, "count": limit, "language": "en", "format": "json"}
    try:
        resp = httpx.get(GEOCODE_URL, params=params, timeout=settings.request_timeout)
        resp.raise_for_status()
        payload = resp.json()
    except httpx.HTTPError as exc:
        log.warning("Geocoding failed for %r: %s", name, exc)
        return None

    results = payload.get("results") or []
    if not results:
        return None

    hit = max(results, key=lambda h: _score_hit(name, h))
    location = _location_from_geonames(hit, fallback_name=name)
    log.debug("Geocoded %r -> %s (%s)", name, location.display_name, location.feature_code)
    cache[key] = location.model_dump()
    _save_cache(cache)
    return location


# --- reverse geocoding -----------------------------------------------------
def _reverse_nominatim(lat: float, lon: float, settings) -> Location | None:
    """Precise local name + address from OpenStreetMap (Nominatim)."""
    params = {
        "format": "jsonv2",
        "lat": lat,
        "lon": lon,
        "zoom": 18,
        "addressdetails": 1,
        "accept-language": "en",
    }
    try:
        resp = httpx.get(
            NOMINATIM_URL,
            params=params,
            timeout=settings.request_timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Nominatim reverse failed for %s,%s: %s", lat, lon, exc)
        return None

    address = data.get("address") or {}
    # Most-local name first: a real village beats a broad city label.
    local = _clean_local(
        address.get("village")
        or address.get("hamlet")
        or address.get("suburb")
        or address.get("neighbourhood")
        or address.get("town")
        or address.get("city")
        or data.get("name")
    )
    if not local and not address:
        return None

    admin2 = address.get("state_district") or address.get("county")
    admin3 = (
        address.get("municipality")
        or address.get("city_district")
        or (address.get("county") if address.get("state_district") else None)
    )

    return Location(
        name=local or "Unknown",
        latitude=lat,
        longitude=lon,
        country=address.get("country"),
        country_code=(address.get("country_code") or "").upper() or None,
        admin1=address.get("state") or address.get("region"),
        admin2=admin2,
        admin3=admin3,
        admin4=_clean_local(address.get("neighbourhood") or address.get("suburb")),
        postcode=address.get("postcode"),
        feature_code="REVERSE",
        source="reverse",
    )


def _reverse_bigdatacloud(lat: float, lon: float, settings) -> Location | None:
    """Timezone + administrative tree from BigDataCloud (no key required)."""
    params = {"latitude": lat, "longitude": lon, "localityLanguage": "en"}
    try:
        resp = httpx.get(
            BIGDATACLOUD_URL,
            params=params,
            timeout=settings.request_timeout,
            follow_redirects=True,
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("BigDataCloud reverse failed for %s,%s: %s", lat, lon, exc)
        return None

    info = data.get("localityInfo") or {}
    informative = info.get("informative") or []
    timezone = next(
        (x.get("name") for x in informative if x.get("description") == "time zone"), None
    )

    name = _clean_local(data.get("locality")) or _clean_local(data.get("city"))
    if not name and not timezone:
        return None

    return Location(
        name=name or data.get("city") or "Unknown",
        latitude=lat,
        longitude=lon,
        country=data.get("countryName"),
        country_code=(data.get("countryCode") or "").upper() or None,
        admin1=data.get("principalSubdivision"),
        postcode=data.get("postcode") or None,
        timezone=timezone,
        feature_code="REVERSE",
        source="reverse",
    )


def _open_meteo_meta(lat: float, lon: float, settings) -> tuple[str | None, float | None]:
    """Timezone + elevation from Open-Meteo (free, key-less).

    This is deliberately the *same* provider the weather stage uses, so the
    timezone that drives sunrise/sunset always matches the forecast.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m",
        "timezone": "auto",
        "forecast_days": 1,
    }
    try:
        resp = httpx.get(
            OPEN_METEO_URL,
            params=params,
            timeout=settings.request_timeout,
            follow_redirects=True,
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Open-Meteo meta lookup failed for %s,%s: %s", lat, lon, exc)
        return None, None
    return data.get("timezone"), data.get("elevation")


def reverse_geocode(latitude: float, longitude: float) -> Location | None:
    """Resolve coordinates to a named place (village / suburb / city).

    Nominatim supplies the precise local name and address; Open-Meteo supplies
    the timezone and elevation; BigDataCloud is a fallback if Nominatim is
    unavailable (it rate-limits). Returns ``None`` if nothing resolves, so
    callers can fall back to a plain coordinate label.
    """
    settings = get_settings()
    key = f"rev:{latitude:.4f},{longitude:.4f}"
    cache = _load_cache()
    if key in cache:
        return Location(**cache[key])

    location = _reverse_nominatim(latitude, longitude, settings)
    if location is None:
        location = _reverse_bigdatacloud(latitude, longitude, settings)
    if location is None:
        log.info("Reverse geocoding found nothing for %s,%s", latitude, longitude)
        return None

    timezone, elevation = _open_meteo_meta(latitude, longitude, settings)
    if not location.timezone:
        location.timezone = timezone
    if location.elevation is None:
        location.elevation = elevation

    location.display_name = _compose_display_name(location)
    log.info("Reverse-geocoded %s,%s -> %s", latitude, longitude, location.display_name)
    cache[key] = location.model_dump()
    _save_cache(cache)
    return location


# --- public entry point ----------------------------------------------------
def resolve_location(
    city: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> Location:
    """Resolve a Location from either a place name or raw coordinates.

    Priority: explicit coordinates > place name > configured default. Coordinates
    are reverse-geocoded to a real place name when possible.
    """
    settings = get_settings()

    if latitude is not None and longitude is not None:
        lat, lon = float(latitude), float(longitude)
        if settings.reverse_geocode_enabled:
            location = reverse_geocode(lat, lon)
            if location is not None:
                return location
        label = city or f"{lat:.3f}, {lon:.3f}"
        return Location(name=label, latitude=lat, longitude=lon, source="coordinates")

    if city:
        location = geocode_city(city)
        if location is not None:
            return location
        log.info("Falling back to default location for unknown place %r", city)

    return Location(
        name=settings.default_location_name,
        latitude=settings.default_latitude,
        longitude=settings.default_longitude,
        source="default",
    )
