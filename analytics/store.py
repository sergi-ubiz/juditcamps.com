"""
Persistència dels esdeveniments d'analítica.

Cloud Run no té disc persistent, així que en producció s'usa Firestore (base
de dades pròpia al projecte, a la UE). En local s'usa un fitxer SQLite.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Protocol

from analytics.domain import Event

logger = logging.getLogger(__name__)


class EventStore(Protocol):
    """Contracte de persistència (permet injectar-ne qualsevol implementació)."""

    def add(self, event: Event) -> None:
        """Desa un esdeveniment nou."""
        ...

    def update_engagement(self, event_id: str, engaged_ms: int,
                          scroll_pct: int) -> None:
        """Actualitza el temps actiu i el desplaçament d'una visita existent."""
        ...

    def query(self, start: datetime, end: datetime) -> list[Event]:
        """Retorna els esdeveniments amb ``start <= ts < end``."""
        ...


class SqliteEventStore:
    """
    Implementació SQLite per a desenvolupament local.

    Example:
        >>> store = SqliteEventStore("/tmp/analytics.sqlite3")
        >>> store.query(start, end)
    """

    def __init__(self, database_path: str) -> None:
        self._database_path = database_path
        self._lock = threading.Lock()
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS analytics_events ("
                " event_id TEXT PRIMARY KEY,"
                " ts TEXT NOT NULL,"
                " payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_analytics_events_ts"
                " ON analytics_events (ts)"
            )
            now = datetime.now(timezone.utc).isoformat()
            connection.execute(
                "DELETE FROM analytics_events"
                " WHERE json_extract(payload, '$.expire_at') < ?",
                (now,),
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._database_path, timeout=10)

    def add(self, event: Event) -> None:
        payload = json.dumps(event.to_dict(), default=_json_default)
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO analytics_events VALUES (?, ?, ?)",
                (event.event_id, event.ts.isoformat(), payload),
            )

    def update_engagement(self, event_id: str, engaged_ms: int,
                          scroll_pct: int) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE analytics_events SET payload = json_set(payload,"
                " '$.engaged_ms', max(json_extract(payload, '$.engaged_ms'), ?),"
                " '$.scroll_pct', max(json_extract(payload, '$.scroll_pct'), ?))"
                " WHERE event_id = ?",
                (engaged_ms, scroll_pct, event_id),
            )

    def query(self, start: datetime, end: datetime) -> list[Event]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM analytics_events"
                " WHERE ts >= ? AND ts < ? ORDER BY ts",
                (start.isoformat(), end.isoformat()),
            ).fetchall()
        return [Event.from_dict(json.loads(row[0])) for row in rows]


class FirestoreEventStore:
    """
    Implementació Firestore per a producció.

    Cada esdeveniment és un document identificat per ``event_id``. El camp
    ``expire_at`` permet activar una política TTL que esborra les dades antigues.
    """

    def __init__(self, database: str, collection: str) -> None:
        from google.cloud import firestore  # Import tardà: només a producció.

        self._client = firestore.Client(database=database)
        self._collection = self._client.collection(collection)
        self._firestore = firestore

    def add(self, event: Event) -> None:
        self._collection.document(event.event_id).create(event.to_dict())

    def update_engagement(self, event_id: str, engaged_ms: int,
                          scroll_pct: int) -> None:
        from google.api_core import exceptions

        document = self._collection.document(event_id)

        @self._firestore.transactional
        def apply_max(transaction) -> None:
            snapshot = document.get(transaction=transaction)
            if not snapshot.exists:
                return
            current = snapshot.to_dict() or {}
            transaction.update(document, {
                "engaged_ms": max(int(current.get("engaged_ms") or 0), engaged_ms),
                "scroll_pct": max(int(current.get("scroll_pct") or 0), scroll_pct),
            })

        try:
            apply_max(self._client.transaction())
        except exceptions.GoogleAPICallError as error:
            logger.warning("No s'ha pogut actualitzar %s: %s", event_id, error)

    def query(self, start: datetime, end: datetime) -> list[Event]:
        documents = (
            self._collection
            .where(filter=self._firestore.FieldFilter("ts", ">=", start))
            .where(filter=self._firestore.FieldFilter("ts", "<", end))
            .order_by("ts")
            .stream()
        )
        return [Event.from_dict(document.to_dict()) for document in documents]


def build_store_from_env() -> EventStore | None:
    """
    Crea la persistència segons ``ANALYTICS_BACKEND`` (``firestore``/``sqlite``).

    Retorna ``None`` si no es pot inicialitzar: l'analítica es desactiva però
    la web i el formulari continuen funcionant.
    """
    backend = os.environ.get("ANALYTICS_BACKEND", "sqlite").lower()
    try:
        if backend == "firestore":
            return FirestoreEventStore(
                database=os.environ.get("ANALYTICS_FIRESTORE_DB", "juditcamps"),
                collection=os.environ.get("ANALYTICS_COLLECTION",
                                          "analytics_events"),
            )
        default_path = os.path.join(os.path.dirname(__file__), "..",
                                    "analytics-local.sqlite3")
        return SqliteEventStore(os.environ.get("ANALYTICS_SQLITE_PATH",
                                               default_path))
    except Exception as error:  # noqa: BLE001 - mai no ha de tombar la web
        logger.error("Analítica desactivada (%s): %s", backend, error)
        return None


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"No serialitzable: {type(value)!r}")
