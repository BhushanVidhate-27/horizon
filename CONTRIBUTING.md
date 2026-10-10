# Contributing to Horizon 🌇

First off — thank you! Horizon is a small, friendly project and contributions of
every size are welcome: a typo fix, a new astronomy dataset, a better weather
score, a translation, or a bug report.

This project follows a [Code of Conduct](CODE_OF_CONDUCT.md). By participating,
you agree to uphold it.

## Ways to help

- 🐛 **Report a bug** or 📈 **request a feature** via
  [issues](https://github.com/your-user/horizon/issues).
- 📖 **Improve the docs** — the README and `docs/` are part of the product.
- 🧪 **Add tests** — the suite is fully offline and fast.
- ✨ **Build something from the [Future improvements](../README.md#-future-improvements) list.**

Good first issues are labelled [`good first issue`](https://github.com/your-user/horizon/labels/good%20first%20issue).

## Development setup

```bash
git clone https://github.com/your-user/horizon && cd horizon
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install pytest pytest-cov ruff
```

Run the app:

```bash
uvicorn horizon.main:app --reload      # http://localhost:8000
python -m horizon.cli --city "Lisbon"  # CLI
```

## Before you open a pull request

```bash
make lint    # ruff check . && ruff format --check .
make test    # pytest (offline, ~1s)
make fmt     # ruff format .   (auto-fix formatting)
```

Or without `make`:

```bash
ruff check . && ruff format --check .
pytest
```

## Guidelines

- **Keep the core key-free.** The whole point is that Open-Meteo + Skyfield +
  an open model deliver a useful result with an empty `.env`. Optional partner
  integrations must always degrade gracefully when their key is absent.
- **Never let a partner call crash the pipeline.** Network, LLM and storage
  failures are logged and skipped — see `horizon/agent.py` for the pattern.
- **Prefer pure functions** for anything you want to test, and keep network
  access behind a small, mockable function.
- **Type hints** everywhere (`from __future__ import annotations`), Pydantic v2
  models for anything crossing the API/CLI boundary.
- **Tests are offline.** Monkeypatch `httpx` rather than hitting the network.
  The Skyfield ephemeris is cached in `.cache/` (downloaded once).
- Keep the diff focused; update the README when behaviour or config changes.

## Commit messages

Short and imperative, e.g. `weather: reward clear skies in the score`,
`docs: add Render deploy notes`, `tests: cover the BigDataCloud fallback`.

## Adding a partner integration

1. Add an optional field to `horizon/config.py` (with a `has_*` property).
2. Create a tiny module under `horizon/` that returns `None`/`[]` when the key
   is missing and never raises.
3. Wire it into `horizon/agent.py` inside its own `_span(...)`.
4. Surface it in `ProviderStatus`, `/api/health`, the web footer and the CLI.
5. Document it in `.env.example` and the README partner table.

Thanks again — now go outside and look up. 🌿
