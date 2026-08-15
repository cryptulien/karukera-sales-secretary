from __future__ import annotations

from typing import Any

from sales_secretary.schemas import ApprovalCard
from sales_secretary.tenant import Tenant
from sales_secretary.writer import apply_card


class FakeOdoo:
    def __init__(self) -> None:
        self.created: list[tuple[str, dict[str, Any]]] = []
        self.posted: list[dict[str, Any]] = []
        self._seq = 10

    def search_read(self, model, domain, fields, limit=5):  # noqa: ANN001
        if model == "res.partner":
            return []
        if model == "crm.lead":
            return []
        if model == "ir.model":
            return [{"id": 88, "model": "crm.lead"}]
        return []

    def create(self, model, vals):  # noqa: ANN001
        self._seq += 1
        self.created.append((model, vals))
        return self._seq

    def execute_kw(self, model, method, args, kwargs=None):  # noqa: ANN001
        if method == "message_post":
            self.posted.append({"model": model, "args": args, "kwargs": kwargs or {}})
            return True
        raise AssertionError(method)

    def close(self) -> None:
        pass


def test_apply_creates_six_surfaces(card: ApprovalCard, tenant: Tenant):
    fake = FakeOdoo()
    ids = apply_card(card, tenant, client=fake)  # type: ignore[arg-type]
    models = [m for m, _ in fake.created]
    assert models.count("res.partner") == 1
    assert models.count("crm.lead") == 1
    assert models.count("mail.activity") == 1
    assert models.count("project.task") == 1
    assert "mail.mail" not in models
    assert ids["partner_id"]
    assert ids["lead_id"]
    assert ids["activity_id"]
    assert ids["task_id"]
    assert ids["mail_draft"] is True
    drafts = [p for p in fake.posted if "BROUILLON MAIL" in p["kwargs"].get("body", "")]
    assert drafts, "le brouillon doit être une note chatter, pas un mail.mail"


def test_apply_is_idempotent_on_existing_ids(card: ApprovalCard, tenant: Tenant):
    fake = FakeOdoo()
    ids = apply_card(
        card,
        tenant,
        client=fake,  # type: ignore[arg-type]
        existing_ids={
            "partner_id": 1,
            "lead_id": 2,
            "activity_id": 3,
            "task_id": 4,
        },
    )
    assert ids["partner_id"] == 1
    assert ids["lead_id"] == 2
    assert not fake.created
    assert fake.posted  # chatter + brouillon toujours (notes)


def test_skip_mail_and_task(card: ApprovalCard, tenant: Tenant):
    card.skip.mail_draft = True
    card.skip.task = True
    fake = FakeOdoo()
    apply_card(card, tenant, client=fake)  # type: ignore[arg-type]
    models = [m for m, _ in fake.created]
    assert "project.task" not in models
    assert not any("BROUILLON MAIL" in p["kwargs"].get("body", "") for p in fake.posted)
