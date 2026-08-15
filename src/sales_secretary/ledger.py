"""Ledger SQLite : un événement = une ligne, jamais de doublon."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from sales_secretary.schemas import EventRecord, EventStatus, utcnow_iso


SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  external_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL,
  card_json TEXT,
  odoo_ids_json TEXT,
  error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (source, external_id)
);
"""


class Ledger:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def insert_new(self, event: EventRecord) -> bool:
        """True si inséré, False si déjà connu."""
        try:
            self._conn.execute(
                """
                INSERT INTO events (
                  id, source, external_id, kind, occurred_at, payload_json,
                  status, card_json, odoo_ids_json, error, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.source,
                    event.external_id,
                    event.kind,
                    event.occurred_at,
                    json.dumps(event.payload, ensure_ascii=False),
                    event.status,
                    json.dumps(event.card, ensure_ascii=False) if event.card else None,
                    json.dumps(event.odoo_ids, ensure_ascii=False)
                    if event.odoo_ids
                    else None,
                    event.error,
                    event.created_at,
                    event.updated_at,
                ),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get(self, event_id: str) -> EventRecord | None:
        row = self._conn.execute(
            "SELECT * FROM events WHERE id = ?", (event_id,)
        ).fetchone()
        return _row_to_event(row) if row else None

    def list(
        self,
        status: EventStatus | None = None,
        limit: int = 50,
    ) -> list[EventRecord]:
        if status:
            rows = self._conn.execute(
                "SELECT * FROM events WHERE status = ? ORDER BY occurred_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM events ORDER BY occurred_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row_to_event(r) for r in rows]

    def update(
        self,
        event_id: str,
        *,
        status: EventStatus | None = None,
        card: dict[str, Any] | None = None,
        odoo_ids: dict[str, Any] | None = None,
        error: str | None = None,
        clear_error: bool = False,
    ) -> EventRecord:
        current = self.get(event_id)
        if current is None:
            raise KeyError(event_id)
        now = utcnow_iso()
        new_status = status or current.status
        new_card = current.card if card is None else card
        new_ids = current.odoo_ids if odoo_ids is None else odoo_ids
        new_error = None if clear_error else (error if error is not None else current.error)
        self._conn.execute(
            """
            UPDATE events
               SET status = ?, card_json = ?, odoo_ids_json = ?, error = ?, updated_at = ?
             WHERE id = ?
            """,
            (
                new_status,
                json.dumps(new_card, ensure_ascii=False) if new_card else None,
                json.dumps(new_ids, ensure_ascii=False) if new_ids else None,
                new_error,
                now,
                event_id,
            ),
        )
        self._conn.commit()
        updated = self.get(event_id)
        assert updated is not None
        return updated

    def counts(self) -> dict[str, int]:
        rows: Iterable[sqlite3.Row] = self._conn.execute(
            "SELECT status, COUNT(*) AS n FROM events GROUP BY status"
        ).fetchall()
        return {r["status"]: r["n"] for r in rows}


def _row_to_event(row: sqlite3.Row) -> EventRecord:
    return EventRecord(
        id=row["id"],
        source=row["source"],
        external_id=row["external_id"],
        kind=row["kind"],
        occurred_at=row["occurred_at"],
        payload=json.loads(row["payload_json"]),
        status=row["status"],
        card=json.loads(row["card_json"]) if row["card_json"] else None,
        odoo_ids=json.loads(row["odoo_ids_json"]) if row["odoo_ids_json"] else None,
        error=row["error"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
