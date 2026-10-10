"""Typed data models shared across Horizon.

Pydantic v2 models keep the API responses, the CLI output and the storage
layer in sync, and give FastAPI automatic request validation + OpenAPI docs.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Location(BaseModel):
    # ``name`` is the most local place name we could resolve — for a GPS fix that
    # means the actual village / neighbourhood, not "12.34, 56.78".
    name: str
    latitude: float
    longitude: float
    country: str | None = None
    country_code: str | None = None
    # Administrative hierarchy, from most local (admin4) to broadest (admin1).
    admin1: str | None = Field(default=None, description="State / province")
    admin2: str | None = Field(default=None, description="District / county")
    admin3: str | None = Field(default=None, description="Sub-district / mandal / municipality")
    admin4: str | None = Field(default=None, description="Village / neighbourhood")
    postcode: str | None = None
    feature_code: str | None = Field(default=None, description="GeoNames feature code, e.g. PPL")
    population: int | None = None
    elevation: float | None = None
    timezone: str | None = None
    # Human-readable hierarchical label, e.g. "Kothaguda, Ranga Reddy, Telangana, India".
    display_name: str | None = None
    source: str = Field(default="geocode", description="geocode | reverse | coordinates | default")


class WeatherWindow(BaseModel):
    """A recommended contiguous outdoor window."""

    start: datetime
    end: datetime
    hours: int
    score: float = Field(ge=0, le=100, description="0-100 outdoor comfort score")
    summary: str
    temperature_c: float
    feels_like_c: float
    precipitation_probability: int
    wind_kph: float
    cloud_cover: int
    uv_index: float


class HourlyPoint(BaseModel):
    """One hour in the day's outdoor-score series (drives the hourly strip)."""

    time: datetime
    score: float = Field(ge=0, le=100)
    temperature_c: float
    feels_like_c: float = 0.0
    precipitation_probability: int
    wind_kph: float = 0.0
    cloud_cover: int
    uv_index: float = 0.0
    icon: str = "sun"
    is_best: bool = False


class CalendarEvent(BaseModel):
    """A notable, plan-around sky event for the in-app calendar."""

    date: str = Field(description="Event date, ISO yyyy-mm-dd")
    title: str
    kind: str = Field(description="moon | meteor | season | planet")
    importance: int = Field(ge=1, le=3, description="1 minor, 2 notable, 3 major")
    detail: str = ""
    time: str | None = Field(default=None, description="Local time, when precise")


class Planet(BaseModel):
    name: str
    altitude_deg: float
    azimuth_deg: float
    direction: str
    magnitude: float | None = None
    visible: bool = False


class Constellation(BaseModel):
    name: str
    star: str
    altitude_deg: float
    direction: str


class MeteorShower(BaseModel):
    name: str
    peak: str
    active: str
    zhr: int = Field(description="Zenithal hourly rate at peak")
    radiant: str
    description: str
    near_peak: bool = False


class SkyEvent(BaseModel):
    kind: str = Field(description="sun | moon | planet | constellation | meteor | news")
    label: str
    detail: str


class SkyReport(BaseModel):
    sunrise: datetime | None = None
    sunset: datetime | None = None
    solar_noon: datetime | None = None
    civil_twilight_end: datetime | None = None
    moon_phase_name: str = "Unknown"
    moon_illumination: float = 0.0
    moon_age_days: float | None = None
    moonrise: datetime | None = None
    moonset: datetime | None = None
    planets: list[Planet] = Field(default_factory=list)
    constellations: list[Constellation] = Field(default_factory=list)
    meteor_showers: list[MeteorShower] = Field(default_factory=list)
    events: list[SkyEvent] = Field(default_factory=list)


class ProviderStatus(BaseModel):
    """Which partner integrations actually contributed to this alert."""

    gemma: bool = False
    elevenlabs: bool = False
    mongodb: bool = False
    serpapi: bool = False
    sentry: bool = False
    hosting: str = "local"
    llm_provider: str | None = None


class DailyAlert(BaseModel):
    location: Location
    generated_at: datetime
    generated_for_date: str
    headline: str
    message: str
    nudge: str
    weather_summary: str
    best_window: WeatherWindow | None = None
    hourly: list[HourlyPoint] = Field(default_factory=list)
    sky_report: SkyReport
    audio_url: str | None = None
    news: list[str] = Field(default_factory=list)
    providers: ProviderStatus = Field(default_factory=ProviderStatus)


class AlertRequest(BaseModel):
    city: str | None = Field(default=None, description="City name, e.g. 'Tokyo'")
    latitude: float | None = None
    longitude: float | None = None
    speak: bool = Field(default=False, description="Also generate ElevenLabs audio")
    use_llm: bool = Field(default=True, description="Narrate with Gemma when available")
