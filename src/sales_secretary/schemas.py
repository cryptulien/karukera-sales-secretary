"""Schémas des événements inbox et des cartes d'approbation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


EventKind = Literal["call", "email"]
EventStatus = Literal["new", "carded", "applied", "ignored", "error"]


class EventRecord(BaseModel):
    id: str
    source: Literal["ringover", "imap"]
    external_id: str
    kind: EventKind
    occurred_at: str
    payload: dict[str, Any]
    status: EventStatus = "new"
    card: dict[str, Any] | None = None
    odoo_ids: dict[str, Any] | None = None
    error: str | None = None
    created_at: str
    updated_at: str


class ContactProposal(BaseModel):
    name: str = ""
    phone: str | None = None
    email: str | None = None
    partner_id: int | None = None
    is_new: bool = True


class LeadProposal(BaseModel):
    name: str
    lead_id: int | None = None
    team_id: int | None = None
    stage_id: int | None = None
    user_id: int | None = None


class ActivityProposal(BaseModel):
    summary: str
    activity_type_id: int | None = None
    date_deadline: str
    user_id: int | None = None


class TaskProposal(BaseModel):
    name: str
    project_id: int | None = None
    user_id: int | None = None
    description: str = ""


class MailDraftProposal(BaseModel):
    subject: str
    body: str
    email_to: str = ""


class SkipFlags(BaseModel):
    activity: bool = False
    task: bool = False
    mail_draft: bool = False


class ApprovalCard(BaseModel):
    event_id: str
    kind: EventKind
    contact: ContactProposal
    lead: LeadProposal
    activity: ActivityProposal | None = None
    task: TaskProposal | None = None
    mail_draft: MailDraftProposal | None = None
    skip: SkipFlags = Field(default_factory=SkipFlags)
    chatter: str = ""
    summary: str = ""


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
