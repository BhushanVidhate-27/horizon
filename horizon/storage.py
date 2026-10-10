"""Persistence layer — MongoDB Atlas with a zero-config local fallback.

Partner category: **Best Use of MongoDB Atlas**.

When ``MONGODB_URI`` is set we use Atlas to store:
  * location preferences (one document per named place)
  * a rolling history of generated daily alerts

When it is not set we transparently fall back to a local SQLite database in
``.cache/horizon.db`` so the app still remembers things during a demo.

Atlas Vector Search hook
------------------------
``search_history`` is written so that dropping in ``$vectorSearch`` (Atlas
Vector Search) is a one-line change once you store embeddings: replace the
``find`` with a ``$vectorSearch`` stage. A ``text`` Atlas Search index on
``message`` also works out of the box with ``$search``.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from .config import get_settings
from .models import DailyAlert, Location

log = logging.getLogger("horizon.storage")


class Storage:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.backend = "mongodb" if self.settings.has_mongodb else "sqlite"
        self._client = None
        self._db = None
        if self.backend == "mongodb":
            self._init_mongo()
        else:
            self._init_sqlite()

    # -- setup -------------------------------------------------------------
    def _init_mongo(self) -> None:  # pragma: no cover - requires a live Atlas URI
        try:
            from pymongo import MongoClient

            self._client = MongoClient(self.settings.mongodb_uri, serverSelectionTimeoutMS=5000)
            self._client.admin.command("ping")
            self._db = self._client[self.settings.mongodb_db]
            log.info("Connected to MongoDB Atlas database %r", self.settings.mongodb_db)
        except Exception as exc:
            log.warning("MongoDB unavailable (%s); falling back to SQLite.", exc)
            self.backend = "sqlite"
            self._client = None
            self._init_sqlite()

    def _init_sqlite(self) -> None:
        path = Path(self.settings.cache_dir)
        path.mkdir(parents=True, exist_ok=True)
        self._sqlite_path = path / "horizon.db"
        conn = sqlite3.connect(self._sqlite_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                generated_at TEXT,
                location TEXT,
                payload TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS locations (
                name TEXT PRIMARY KEY,
                payload TEXT
            )
            """
        )
        conn.commit()
        conn.close()

    # -- alerts ------------------------------------------------------------
    def save_alert(self, alert: DailyAlert) -> None:
        doc = json.loads(alert.model_dump_json())
        if self.backend == "mongodb":  # pragma: no cover - live Atlas only
            self._db.alerts.insert_one(doc)
            return
        conn = sqlite3.connect(self._sqlite_path)
        conn.execute(
            "INSERT INTO alerts (generated_at, location, payload) VALUES (?, ?, ?)",
            (doc["generated_at"], doc["location"]["name"], json.dumps(doc)),
        )
        conn.commit()
        conn.close()

    def recent_alerts(
        self, limit: int = 5, location_name: str | None = None
    ) -> list[dict[str, Any]]:
        if self.backend == "mongodb":  # pragma: no cover - live Atlas only
            query = {"location.name": location_name} if location_name else {}
            cursor = self._db.alerts.find(query, {"_id": 0}).sort("generated_at", -1).limit(limit)
            return list(cursor)
        conn = sqlite3.connect(self._sqlite_path)
        if location_name:
            rows = conn.execute(
                "SELECT payload FROM alerts WHERE location = ? ORDER BY id DESC LIMIT ?",
                (location_name, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT payload FROM alerts ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        conn.close()
        return [json.loads(r[0]) for r in rows]

    def search_history(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Very small full-text-ish search.

        Swap the Mongo branch for Atlas Vector Search / Atlas Search in prod.
        """
        if self.backend == "mongodb":  # pragma: no cover - live Atlas only
            cursor = self._db.alerts.find(
                {"message": {"$regex": query, "$options": "i"}}, {"_id": 0}
            ).limit(limit)
            return list(cursor)
        conn = sqlite3.connect(self._sqlite_path)
        rows = conn.execute(
            "SELECT payload FROM alerts WHERE payload LIKE ? ORDER BY id DESC LIMIT ?",
            (f"%{query}%", limit),
        ).fetchall()
        conn.close()
        return [json.loads(r[0]) for r in rows]

    # -- location preferences ---------------------------------------------
    def save_location_pref(self, name: str, location: Location) -> None:
        payload = location.model_dump()
        if self.backend == "mongodb":  # pragma: no cover - live Atlas only
            self._db.locations.update_one(
                {"name": name}, {"$set": {"name": name, **payload}}, upsert=True
            )
            return
        conn = sqlite3.connect(self._sqlite_path)
        conn.execute(
            "INSERT INTO locations (name, payload) VALUES (?, ?) "
            "ON CONFLICT(name) DO UPDATE SET payload = excluded.payload",
            (name, json.dumps(payload)),
        )
        conn.commit()
        conn.close()

    def get_location_pref(self, name: str) -> Location | None:
        if self.backend == "mongodb":  # pragma: no cover - live Atlas only
            doc = self._db.locations.find_one({"name": name}, {"_id": 0})
            if doc:
                doc.pop("name", None)
                return Location(**doc)
            return None
        conn = sqlite3.connect(self._sqlite_path)
        row = conn.execute("SELECT payload FROM locations WHERE name = ?", (name,)).fetchone()
        conn.close()
        return Location(**json.loads(row[0])) if row else None

    def stats(self) -> dict[str, Any]:
        if self.backend == "mongodb":  # pragma: no cover - live Atlas only
            return {
                "backend": "mongodb",
                "alerts": self._db.alerts.count_documents({}),
                "locations": self._db.locations.count_documents({}),
            }
        conn = sqlite3.connect(self._sqlite_path)
        alerts = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
        locations = conn.execute("SELECT COUNT(*) FROM locations").fetchone()[0]
        conn.close()
        return {"backend": "sqlite", "alerts": alerts, "locations": locations}
