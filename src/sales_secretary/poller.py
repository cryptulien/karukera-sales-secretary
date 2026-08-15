"""Cycle d'ingest : Ringover + IMAP → ledger."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sales_secretary.imap_poll import harvest_imap
from sales_secretary.ledger import Ledger
from sales_secretary.ringover import RingoverClient
from sales_secretary.schemas import EventRecord
from sales_secretary.tenant import Tenant, load_tenant

log = logging.getLogger("sales_secretary.poller")


def poll_once(data_dir: Path, tenant: Tenant | None = None) -> dict[str, Any]:
    tenant = tenant or load_tenant(data_dir)
    if tenant is None:
        return {"ok": False, "error": "tenant.yaml absent"}
    ledger = Ledger(data_dir / "ledger.sqlite")
    inserted = 0
    errors: list[str] = []
    try:
        if tenant.ringover:
            try:
                client = RingoverClient(tenant.ringover)
                try:
                    events = client.harvest(lookback_hours=tenant.poll.lookback_hours)
                finally:
                    client.close()
                inserted += _store(ledger, events)
            except Exception as exc:  # noqa: BLE001 — on isole la source
                log.exception("poll ringover")
                errors.append(f"ringover: {exc}")
        if tenant.imap:
            try:
                events = harvest_imap(tenant.imap)
                inserted += _store(ledger, events)
            except Exception as exc:  # noqa: BLE001
                log.exception("poll imap")
                errors.append(f"imap: {exc}")
    finally:
        ledger.close()
    return {
        "ok": not errors,
        "inserted": inserted,
        "errors": errors,
        "counts": Ledger(data_dir / "ledger.sqlite").counts(),
    }


def _store(ledger: Ledger, events: list[EventRecord]) -> int:
    n = 0
    for event in events:
        if ledger.insert_new(event):
            n += 1
    return n
