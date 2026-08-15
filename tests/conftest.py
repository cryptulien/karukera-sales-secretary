from __future__ import annotations

from pathlib import Path

import pytest

from sales_secretary.schemas import (
    ActivityProposal,
    ApprovalCard,
    ContactProposal,
    LeadProposal,
    MailDraftProposal,
    TaskProposal,
)
from sales_secretary.tenant import (
    ImapConfig,
    OdooConfig,
    OdooDefaults,
    RingoverConfig,
    Tenant,
    save_tenant,
)


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture
def tenant(data_dir: Path) -> Tenant:
    t = Tenant(
        odoo=OdooConfig(
            url="https://odoo.example.com",
            db="acme",
            username="api@acme.test",
            api_key="secret",
            defaults=OdooDefaults(
                user_id=2,
                team_id=1,
                stage_id=3,
                project_id=7,
                activity_type_call=4,
                activity_type_todo=5,
            ),
        ),
        ringover=RingoverConfig(api_key="rk_test"),
        imap=ImapConfig(
            host="imap.example.com",
            username="box@acme.test",
            password="app-pass",
        ),
    )
    save_tenant(data_dir, t)
    return t


@pytest.fixture
def card() -> ApprovalCard:
    return ApprovalCard(
        event_id="ringover:call:99",
        kind="call",
        contact=ContactProposal(
            name="Marie Dupont",
            phone="+33612345678",
            email="marie@dupont.test",
            is_new=True,
        ),
        lead=LeadProposal(name="Devis cuisine — Dupont"),
        activity=ActivityProposal(
            summary="Rappeler pour le devis",
            date_deadline="2026-08-14",
        ),
        task=TaskProposal(name="Relancer devis", description="Jeudi matin"),
        mail_draft=MailDraftProposal(
            subject="Suite à votre appel",
            body="Bonjour Marie,\n\nJe reviens vers vous.",
            email_to="marie@dupont.test",
        ),
        chatter="A rappelé pour le devis cuisine.",
        summary="Devis cuisine, dispo jeudi.",
    )
