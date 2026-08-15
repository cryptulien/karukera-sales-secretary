from pathlib import Path

from sales_secretary.ledger import Ledger
from sales_secretary.schemas import EventRecord, utcnow_iso


def _event(eid: str = "ringover:call:1") -> EventRecord:
    now = utcnow_iso()
    return EventRecord(
        id=eid,
        source="ringover",
        external_id=eid.split(":")[-1],
        kind="call",
        occurred_at=now,
        payload={"phone": "+33600000000"},
        created_at=now,
        updated_at=now,
    )


def test_insert_is_idempotent(tmp_path: Path):
    ledger = Ledger(tmp_path / "l.sqlite")
    assert ledger.insert_new(_event()) is True
    assert ledger.insert_new(_event()) is False
    assert ledger.list()[0].status == "new"


def test_update_card_and_apply(tmp_path: Path):
    ledger = Ledger(tmp_path / "l.sqlite")
    ledger.insert_new(_event())
    ledger.update("ringover:call:1", status="carded", card={"event_id": "ringover:call:1"})
    applied = ledger.update(
        "ringover:call:1",
        status="applied",
        odoo_ids={"lead_id": 12},
    )
    assert applied.status == "applied"
    assert applied.odoo_ids == {"lead_id": 12}
    assert ledger.counts()["applied"] == 1
