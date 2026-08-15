"""API HTTP locale : Hermes ne parle qu'à ça."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from sales_secretary.imap_poll import ImapError, ping_imap
from sales_secretary.ledger import Ledger
from sales_secretary.odoo_client import OdooClient, OdooError
from sales_secretary.onboard import load_state, reset_state, submit, view
from sales_secretary.poller import poll_once
from sales_secretary.ringover import RingoverClient, RingoverError
from sales_secretary.schemas import ApprovalCard
from sales_secretary.tenant import (
    ImapConfig,
    OdooConfig,
    RingoverConfig,
    Tenant,
    load_tenant,
    public_tenant,
    save_tenant,
)
from sales_secretary.writer import apply_card, match_open_lead, match_partner


def data_dir() -> Path:
    return Path(os.environ.get("SECRETARY_DATA", "/data"))


def get_ledger() -> Ledger:
    return Ledger(data_dir() / "ledger.sqlite")


def _check_token(authorization: str | None = Header(default=None)) -> None:
    expected = os.environ.get("SECRETARY_TOKEN", "").strip()
    if not expected:
        return
    if authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="token invalide")


@asynccontextmanager
async def lifespan(app: FastAPI):
    data_dir().mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="sales-secretary", lifespan=lifespan)


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.get("/status")
def status(_: None = Depends(_check_token)) -> dict[str, Any]:
    tenant = load_tenant(data_dir())
    ledger = get_ledger()
    try:
        onboard = view(load_state(data_dir()))
        return {
            **public_tenant(tenant),
            "counts": ledger.counts(),
            "onboard": onboard.model_dump(),
        }
    finally:
        ledger.close()


@app.get("/inbox")
def list_inbox(
    status: str | None = None,
    limit: int = 50,
    _: None = Depends(_check_token),
) -> dict[str, Any]:
    ledger = get_ledger()
    try:
        items = ledger.list(status=status, limit=limit)  # type: ignore[arg-type]
        return {"items": [i.model_dump() for i in items]}
    finally:
        ledger.close()


@app.get("/inbox/{event_id:path}")
def get_inbox(event_id: str, _: None = Depends(_check_token)) -> dict[str, Any]:
    ledger = get_ledger()
    try:
        event = ledger.get(event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="événement inconnu")
        return event.model_dump()
    finally:
        ledger.close()


class CardBody(BaseModel):
    card: dict[str, Any]


@app.post("/inbox/{event_id:path}/card")
def save_card(event_id: str, body: CardBody, _: None = Depends(_check_token)) -> dict[str, Any]:
    card = ApprovalCard.model_validate({**body.card, "event_id": event_id})
    ledger = get_ledger()
    try:
        if ledger.get(event_id) is None:
            raise HTTPException(status_code=404, detail="événement inconnu")
        updated = ledger.update(event_id, status="carded", card=card.model_dump(), clear_error=True)
        return updated.model_dump()
    except KeyError:
        raise HTTPException(status_code=404, detail="événement inconnu") from None
    finally:
        ledger.close()


@app.post("/inbox/{event_id:path}/apply")
def apply_inbox(event_id: str, body: CardBody | None = None, _: None = Depends(_check_token)) -> dict[str, Any]:
    tenant = load_tenant(data_dir())
    if tenant is None or tenant.odoo is None:
        raise HTTPException(status_code=409, detail="Odoo non configuré")
    ledger = get_ledger()
    try:
        event = ledger.get(event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="événement inconnu")
        if event.status == "ignored":
            raise HTTPException(status_code=409, detail="événement ignoré")
        raw_card = (body.card if body and body.card else None) or event.card
        if not raw_card:
            raise HTTPException(status_code=409, detail="pas de carte à appliquer")
        card = ApprovalCard.model_validate({**raw_card, "event_id": event_id})
        try:
            odoo_ids = apply_card(card, tenant, existing_ids=event.odoo_ids)
        except Exception as exc:  # noqa: BLE001
            ledger.update(event_id, status="error", error=str(exc))
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        updated = ledger.update(
            event_id,
            status="applied",
            card=card.model_dump(),
            odoo_ids=odoo_ids,
            clear_error=True,
        )
        return updated.model_dump()
    finally:
        ledger.close()


@app.post("/inbox/{event_id:path}/ignore")
def ignore_inbox(event_id: str, _: None = Depends(_check_token)) -> dict[str, Any]:
    ledger = get_ledger()
    try:
        if ledger.get(event_id) is None:
            raise HTTPException(status_code=404, detail="événement inconnu")
        return ledger.update(event_id, status="ignored", clear_error=True).model_dump()
    finally:
        ledger.close()


@app.post("/poll")
def poll(_: None = Depends(_check_token)) -> dict[str, Any]:
    return poll_once(data_dir())


@app.get("/onboard")
def get_onboard(_: None = Depends(_check_token)) -> dict[str, Any]:
    return view(load_state(data_dir())).model_dump()


class OnboardAnswer(BaseModel):
    answer: str


@app.post("/onboard")
def post_onboard(body: OnboardAnswer, _: None = Depends(_check_token)) -> dict[str, Any]:
    return submit(data_dir(), body.answer).model_dump()


@app.post("/onboard/reset")
def post_onboard_reset(_: None = Depends(_check_token)) -> dict[str, Any]:
    return view(reset_state(data_dir())).model_dump()


@app.get("/tenant")
def get_tenant(_: None = Depends(_check_token)) -> dict[str, Any]:
    return public_tenant(load_tenant(data_dir()))


@app.put("/tenant")
def put_tenant(payload: dict[str, Any], _: None = Depends(_check_token)) -> dict[str, Any]:
    tenant = Tenant.model_validate(payload)
    save_tenant(data_dir(), tenant)
    return public_tenant(tenant)


class ProbeOdooBody(BaseModel):
    url: str
    db: str
    username: str
    api_key: str


@app.post("/onboard/probe-odoo")
def probe_odoo(body: ProbeOdooBody, _: None = Depends(_check_token)) -> dict[str, Any]:
    client = OdooClient(OdooConfig(**body.model_dump()))
    try:
        return client.probe()
    except OdooError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        client.close()


class ProbeRingoverBody(BaseModel):
    api_key: str
    base_url: str = "https://public-api.ringover.com/v2"


@app.post("/onboard/probe-ringover")
def probe_ringover(body: ProbeRingoverBody, _: None = Depends(_check_token)) -> dict[str, Any]:
    client = RingoverClient(RingoverConfig(**body.model_dump()))
    try:
        return client.ping()
    except RingoverError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        client.close()


class ProbeImapBody(BaseModel):
    host: str
    username: str
    password: str
    port: int = 993
    folder: str = "INBOX"
    use_ssl: bool = True


@app.post("/onboard/probe-imap")
def probe_imap(body: ProbeImapBody, _: None = Depends(_check_token)) -> dict[str, Any]:
    try:
        return ping_imap(ImapConfig(**body.model_dump()))
    except ImapError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


class MatchBody(BaseModel):
    phone: str | None = None
    email: str | None = None


@app.post("/odoo/match")
def odoo_match(body: MatchBody, _: None = Depends(_check_token)) -> dict[str, Any]:
    tenant = load_tenant(data_dir())
    if tenant is None or tenant.odoo is None:
        raise HTTPException(status_code=409, detail="Odoo non configuré")
    client = OdooClient(tenant.odoo)
    try:
        partner = match_partner(client, body.phone, body.email)
        lead = match_open_lead(client, int(partner["id"])) if partner else None
        return {"partner": partner, "lead": lead}
    except OdooError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        client.close()


