"""Writer Odoo : applique une carte validée. Jamais d'envoi de mail."""

from __future__ import annotations

import html
from typing import Any

from sales_secretary.odoo_client import OdooClient
from sales_secretary.phones import phone_search_tail
from sales_secretary.schemas import ApprovalCard
from sales_secretary.tenant import OdooConfig, Tenant


def apply_card(
    card: ApprovalCard,
    tenant: Tenant,
    client: OdooClient | None = None,
    existing_ids: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if tenant.odoo is None:
        raise RuntimeError("Odoo n'est pas configuré")
    own = client is None
    odoo = client or OdooClient(tenant.odoo)
    ids = dict(existing_ids or {})
    try:
        partner_id = _ensure_partner(odoo, card, ids)
        ids["partner_id"] = partner_id
        lead_id = _ensure_lead(odoo, tenant.odoo, card, partner_id, ids)
        ids["lead_id"] = lead_id
        if card.chatter or card.summary:
            _post_chatter(odoo, lead_id, card)
            ids["chatter"] = True
        if card.mail_draft and not card.skip.mail_draft:
            _post_mail_draft(odoo, lead_id, card)
            ids["mail_draft"] = True
        if card.activity and not card.skip.activity:
            if not ids.get("activity_id"):
                ids["activity_id"] = _create_activity(odoo, tenant.odoo, card, lead_id)
        if card.task and not card.skip.task:
            if not ids.get("task_id"):
                ids["task_id"] = _create_task(odoo, tenant.odoo, card, partner_id)
        return ids
    finally:
        if own:
            odoo.close()


def match_partner(client: OdooClient, phone: str | None, email: str | None) -> dict[str, Any] | None:
    domain: list[Any] = []
    tail = phone_search_tail(phone)
    if tail and email:
        domain = [
            "|",
            "|",
            ("phone", "ilike", tail),
            ("mobile", "ilike", tail),
            ("email", "=ilike", email),
        ]
    elif tail:
        domain = ["|", ("phone", "ilike", tail), ("mobile", "ilike", tail)]
    elif email:
        domain = [("email", "=ilike", email)]
    else:
        return None
    rows = client.search_read(
        "res.partner",
        domain,
        ["name", "phone", "mobile", "email"],
        limit=1,
    )
    return rows[0] if rows else None


def match_open_lead(client: OdooClient, partner_id: int) -> dict[str, Any] | None:
    rows = client.search_read(
        "crm.lead",
        [
            ("partner_id", "=", partner_id),
            ("active", "=", True),
            ("probability", "<", 100),
        ],
        ["name", "stage_id", "user_id"],
        limit=1,
    )
    return rows[0] if rows else None


def _ensure_partner(odoo: OdooClient, card: ApprovalCard, ids: dict[str, Any]) -> int:
    if ids.get("partner_id"):
        return int(ids["partner_id"])
    if card.contact.partner_id:
        return int(card.contact.partner_id)
    found = match_partner(odoo, card.contact.phone, card.contact.email)
    if found:
        return int(found["id"])
    vals: dict[str, Any] = {"name": card.contact.name or card.contact.email or card.contact.phone or "Contact"}
    if card.contact.phone:
        vals["mobile"] = card.contact.phone
    if card.contact.email:
        vals["email"] = card.contact.email
    return odoo.create("res.partner", vals)


def _ensure_lead(
    odoo: OdooClient,
    cfg: OdooConfig,
    card: ApprovalCard,
    partner_id: int,
    ids: dict[str, Any],
) -> int:
    if ids.get("lead_id"):
        return int(ids["lead_id"])
    if card.lead.lead_id:
        return int(card.lead.lead_id)
    existing = match_open_lead(odoo, partner_id)
    if existing:
        return int(existing["id"])
    vals: dict[str, Any] = {
        "name": card.lead.name,
        "partner_id": partner_id,
        "type": "opportunity",
    }
    if card.contact.phone:
        vals["phone"] = card.contact.phone
    if card.contact.email:
        vals["email_from"] = card.contact.email
    user_id = card.lead.user_id or cfg.defaults.user_id
    team_id = card.lead.team_id or cfg.defaults.team_id
    stage_id = card.lead.stage_id or cfg.defaults.stage_id
    if user_id:
        vals["user_id"] = user_id
    if team_id:
        vals["team_id"] = team_id
    if stage_id:
        vals["stage_id"] = stage_id
    return odoo.create("crm.lead", vals)


def _post_chatter(odoo: OdooClient, lead_id: int, card: ApprovalCard) -> None:
    body = card.chatter or card.summary
    if not body:
        return
    odoo.execute_kw(
        "crm.lead",
        "message_post",
        [lead_id],
        {
            "body": _to_html(body),
            "message_type": "comment",
            "subtype_xmlid": "mail.mt_note",
        },
    )


def _post_mail_draft(odoo: OdooClient, lead_id: int, card: ApprovalCard) -> None:
    """Note chatter — Odoo enverrait un mail.mail state=outgoing via son cron."""
    draft = card.mail_draft
    if draft is None:
        return
    block = (
        "<p><b>BROUILLON MAIL — non envoyé</b></p>"
        f"<p>À : {html.escape(draft.email_to or card.contact.email or '')}<br/>"
        f"Objet : {html.escape(draft.subject)}</p>"
        f"{_to_html(draft.body)}"
    )
    odoo.execute_kw(
        "crm.lead",
        "message_post",
        [lead_id],
        {
            "body": block,
            "message_type": "comment",
            "subtype_xmlid": "mail.mt_note",
        },
    )


def _create_activity(
    odoo: OdooClient,
    cfg: OdooConfig,
    card: ApprovalCard,
    lead_id: int,
) -> int:
    assert card.activity is not None
    type_id = (
        card.activity.activity_type_id
        or cfg.defaults.activity_type_todo
        or cfg.defaults.activity_type_call
    )
    user_id = card.activity.user_id or cfg.defaults.user_id
    vals: dict[str, Any] = {
        "res_model_id": _model_id(odoo, "crm.lead"),
        "res_id": lead_id,
        "summary": card.activity.summary,
        "date_deadline": card.activity.date_deadline,
    }
    if type_id:
        vals["activity_type_id"] = type_id
    if user_id:
        vals["user_id"] = user_id
    return odoo.create("mail.activity", vals)


def _create_task(
    odoo: OdooClient,
    cfg: OdooConfig,
    card: ApprovalCard,
    partner_id: int,
) -> int:
    assert card.task is not None
    project_id = card.task.project_id or cfg.defaults.project_id
    user_id = card.task.user_id or cfg.defaults.user_id
    vals: dict[str, Any] = {
        "name": card.task.name,
        "partner_id": partner_id,
        "description": _to_html(card.task.description or card.summary),
    }
    if project_id:
        vals["project_id"] = project_id
    if user_id:
        vals["user_ids"] = [(6, 0, [user_id])]
    return odoo.create("project.task", vals)


def _model_id(odoo: OdooClient, model: str) -> int:
    rows = odoo.search_read("ir.model", [("model", "=", model)], ["id"], limit=1)
    if not rows:
        raise RuntimeError(f"modèle Odoo introuvable: {model}")
    return int(rows[0]["id"])


def _to_html(text: str) -> str:
    escaped = html.escape(text)
    return "<p>" + escaped.replace("\n", "<br/>") + "</p>"
