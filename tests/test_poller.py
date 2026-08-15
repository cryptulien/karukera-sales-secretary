from pathlib import Path

from sales_secretary.ledger import Ledger
from sales_secretary.poller import poll_once
from sales_secretary.schemas import EventRecord, utcnow_iso
from sales_secretary.tenant import Tenant


def test_poll_without_tenant(tmp_path: Path):
    out = poll_once(tmp_path)
    assert out["ok"] is False
    assert "tenant" in out["error"]


def test_poll_stores_ringover(monkeypatch, data_dir: Path, tenant: Tenant):
    now = utcnow_iso()
    event = EventRecord(
        id="ringover:call:1",
        source="ringover",
        external_id="1",
        kind="call",
        occurred_at=now,
        payload={"phone": "+33600000000"},
        created_at=now,
        updated_at=now,
    )

    class FakeClient:
        def harvest(self, lookback_hours=48, limit=50):  # noqa: ANN001
            return [event]

        def close(self) -> None:
            pass

    monkeypatch.setattr("sales_secretary.poller.RingoverClient", lambda cfg: FakeClient())
    monkeypatch.setattr("sales_secretary.poller.harvest_imap", lambda cfg: [])
    out = poll_once(data_dir, tenant)
    assert out["inserted"] == 1
    assert poll_once(data_dir, tenant)["inserted"] == 0
    assert Ledger(data_dir / "ledger.sqlite").get("ringover:call:1") is not None
