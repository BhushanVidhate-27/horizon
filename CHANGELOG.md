# Changelog

All notable changes to Horizon are documented here. The format is loosely based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Interactive **sky calendar** (new/full moons, meteor peaks, equinoxes,
  solstices, planet oppositions) with tap-to-read details.
- **Hourly score strip** and expandable detail tiles (sun arc, moon, planets,
  constellations, conditions, meteors).
- **Dark & light themes** with a remembered preference.
- Village-level **reverse geocoding** (Nominatim → BigDataCloud → Open-Meteo)
  with an on-disk cache, plus a precise → network-fallback geolocation flow.
- `/api/health`, `/api/events`, `/api/history` and `/api/stats` endpoints.
- GitHub Actions CI (lint + tests on Python 3.10–3.12 + a packaging smoke test).
- Offline test suite expanded to ~83 tests (**~95% coverage**).
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, issue & PR templates.

### Fixed

- **Weather score rewarded cloud cover instead of clear skies** — the cloud
  term is now inverted so clear nights score higher (regression test added).
- Meteor showers that peak in early January are now found from late December
  (adjacent-year wrap-around).
- Geocoding now lets an exact-name match always beat a larger, merely similar
  place name.
- News headlines are whitespace-trimmed and empty titles skipped.

### Changed

- Adopted `ruff` lint + formatter (clean on a curated ruleset) and `pytest-cov`.

## [0.1.0] — 2026-10-10

### Added

- First release: daily outside alert & sky event planner.
- Open-Meteo weather window scoring; Skyfield sky report (sun, moon, planets,
  constellations, meteor showers); Gemma narration with a template fallback.
- Optional ElevenLabs voice, SerpApi news, MongoDB Atlas storage (SQLite
  fallback) and Sentry tracing.
- FastAPI web app with an immersive sky UI, plus a matching CLI.
- Docker, DigitalOcean App Platform and Render deploy specs.
