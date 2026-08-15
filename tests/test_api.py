from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sales_secretary import api
from sales_secretary.ledger import Ledger
from sales_secretary.schemas import EventRecord, utcnow_iso
from sales_secretary.tenant import Tenant, save_tenant


@pytest.fixture
def client(data_dir: Path, tenant: Tenant, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("SECRETARY_DATA", str(data_dir))
    monkeypatch.delenv("SECRETARY_TOKEN", raising=False)
    return TestClient(api.app)


def _seed_event(data_dir: Path) -> str:
    now = utcnow_iso()
    event = EventRecord(
        id="ringover:call:7",
        source="ringover",
        external_id="7",
        kind="call",
        occurred_at=now,
        payload={"phone": "+33612345678", "transcript": "devis"},
        created_at=now,
        updated_at=now,
    )
    ledger = Ledger(data_dir / "ledger.sqlite")
    ledger.insert_new(event)
    ledger.close()
    return event.id


def test_healthz(client: TestClient):
    assert client.get("/healthz").json() == {"ok": True}


def test_status_reads_tenant(client: TestClient):
    body = client.get("/status").json()
    assert body["configured"] is True
    assert body["odoo"] is True


def test_card_then_ignore(client: TestClient, data_dir: Path, card):
    eid = _seed_event(data_dir)
    r = client.post(f"/inbox/{eid}/card", json={"card": card.model_dump()})
    assert r.status_code == 200
    assert r.json()["status"] == "carded"
    r = client.post(f"/inbox/{eid}/ignore")
    assert r.json()["status"] == "ignored"


def test_apply_uses_writer(client: TestClient, data_dir: Path, card, monkeypatch: pytest.MonkeyPatch):
    eid = _seed_event(data_dir)

    def fake_apply(c, tenant, client=None, existing_ids=None):  # noqa: ANN001
        return {"partner_id": 1, "lead_id": 2, "activity_id": 3, "task_id": 4, "mail_draft": True}

    monkeypatch.setattr(api, "apply_card", fake_apply)
    client.post(f"/inbox/{eid}/card", json={"card": card.model_dump()})
    r = client.post(f"/inbox/{eid}/apply")
    assert r.status_code == 200
    assert r.json()["status"] == "applied"
    assert r.json()["odoo_ids"]["lead_id"] == 2


def test_onboard_get_starts_at_first_step(client: TestClient):
    body = client.get("/onboard").json()
    assert body["step"] == "odoo_url"
    assert body["done"] is False
    assert "Étape 1/" in body["say"]


def test_token_required(data_dir: Path, tenant: Tenant, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SECRETARY_DATA", str(data_dir))
    monkeypatch.setenv("SECRETARY_TOKEN", "s3cret")
    c = TestClient(api.app)
    assert c.get("/status").status_code == 401
    assert c.get("/status", headers={"Authorization": "Bearer s3cret"}).status_code == 200
