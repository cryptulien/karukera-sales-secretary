"""Wizard d'onboarding figé. L'IA ne choisit pas l'ordre : elle pose `say`."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field

from sales_secretary.imap_poll import ping_imap
from sales_secretary.odoo_client import OdooClient
from sales_secretary.ringover import RingoverClient
from sales_secretary.tenant import (
    ImapConfig,
    OdooConfig,
    OdooDefaults,
    RingoverConfig,
    Tenant,
    save_tenant,
)

STEPS = (
    "odoo_url",
    "odoo_db",
    "odoo_username",
    "odoo_api_key",
    "odoo_user",
    "odoo_team",
    "odoo_stage",
    "odoo_project",
    "odoo_activity_call",
    "odoo_activity_todo",
    "ringover_key",
    "imap_host",
    "imap_user",
    "imap_pass",
    "imap_folder",
    "done",
)

PROMPTS: dict[str, tuple[str, str]] = {
    "odoo_url": (
        "URL de ton Odoo, avec https",
        "Exemple : https://acme.odoo.com — sans slash final.",
    ),
    "odoo_db": (
        "Nom de la base Odoo (champ Database)",
        "Souvent le même que le sous-domaine, ex. acme.",
    ),
    "odoo_username": (
        "Login du compte API Odoo (un email)",
        "Un utilisateur interne, pas un portail client.",
    ),
    "odoo_api_key": (
        "Clé API Odoo de ce compte",
        "Odoo → Préférences → Sécurité du compte → Clés API.",
    ),
    "odoo_user": (
        "Quel commercial reçoit les activités ? Réponds par le numéro.",
        "Un seul choix.",
    ),
    "odoo_team": (
        "Quelle équipe CRM ? Numéro, ou « skip » s'il n'y en a qu'une implicite.",
        "",
    ),
    "odoo_stage": (
        "Colonne / étape par défaut pour un nouveau lead ? Numéro.",
        "En général la première colonne (Nouveau).",
    ),
    "odoo_project": (
        "Projet Odoo pour les tâches de suivi ? Numéro.",
        "Le module Projet doit être installé.",
    ),
    "odoo_activity_call": (
        "Type d'activité « Appel » ? Numéro.",
        "",
    ),
    "odoo_activity_todo": (
        "Type d'activité « À faire » ? Numéro.",
        "",
    ),
    "ringover_key": (
        "Clé API Ringover / Quicktalk",
        "Dashboard Ringover → Developer → API key. Coche Empower pour les transcriptions.",
    ),
    "imap_host": (
        "Serveur IMAP",
        "Gmail : imap.gmail.com — Outlook : outlook.office365.com",
    ),
    "imap_user": (
        "Identifiant IMAP (l'adresse mail)",
        "",
    ),
    "imap_pass": (
        "Mot de passe d'application IMAP",
        "Pas le mot de passe du compte. Gmail : compte Google → Validation en 2 étapes → Mots de passe des applications.",
    ),
    "imap_folder": (
        "Dossier à lire (défaut INBOX). Envoie INBOX si tu ne sais pas.",
        "",
    ),
    "done": (
        "Configuration enregistrée. Crée le cron sales-inbox s'il n'existe pas encore.",
        "",
    ),
}


class Choice(BaseModel):
    id: str
    label: str


class View(BaseModel):
    step: str
    index: int
    total: int
    done: bool
    say: str
    hint: str = ""
    choices: list[Choice] | None = None
    error: str | None = None
    create_cron: bool = False


class State(BaseModel):
    step: str = "odoo_url"
    draft: dict[str, Any] = Field(default_factory=dict)
    probe_odoo: dict[str, Any] | None = None
    error: str | None = None
    done: bool = False


class ProbeFns(Protocol):
    def odoo(self, cfg: OdooConfig) -> dict[str, Any]: ...
    def ringover(self, cfg: RingoverConfig) -> dict[str, Any]: ...
    def imap(self, cfg: ImapConfig) -> dict[str, Any]: ...


@dataclass
class LiveProbes:
    def odoo(self, cfg: OdooConfig) -> dict[str, Any]:
        client = OdooClient(cfg)
        try:
            return client.probe()
        finally:
            client.close()

    def ringover(self, cfg: RingoverConfig) -> dict[str, Any]:
        client = RingoverClient(cfg)
        try:
            return client.ping()
        finally:
            client.close()

    def imap(self, cfg: ImapConfig) -> dict[str, Any]:
        return ping_imap(cfg)


def state_path(data_dir: Path) -> Path:
    return data_dir / "onboard.json"


def load_state(data_dir: Path) -> State:
    path = state_path(data_dir)
    if not path.exists():
        return State()
    return State.model_validate(json.loads(path.read_text(encoding="utf-8")))


def save_state(data_dir: Path, state: State) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    path = state_path(data_dir)
    path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    path.chmod(0o600)


def reset_state(data_dir: Path) -> State:
    state = State()
    save_state(data_dir, state)
    return state


def view(state: State) -> View:
    step = state.step
    index = STEPS.index(step) + 1 if step in STEPS else 1
    title, hint = PROMPTS[step]
    say = f"Étape {index}/{len(STEPS)} — {title}"
    if state.error:
        say = f"{state.error}\n\n{say}"
    choices = _choices_for(state)
    return View(
        step=step,
        index=index,
        total=len(STEPS),
        done=state.done,
        say=say,
        hint=hint,
        choices=choices or None,
        error=state.error,
        create_cron=state.done,
    )


def submit(
    data_dir: Path,
    answer: str,
    probes: ProbeFns | None = None,
) -> View:
    state = load_state(data_dir)
    if state.done:
        return view(state)
    probes = probes or LiveProbes()
    try:
        state = _advance(state, answer.strip(), probes)
        state.error = None
        if state.step == "done":
            _persist_tenant(data_dir, state)
            state.done = True
    except OnboardError as exc:
        state.error = str(exc)
    save_state(data_dir, state)
    return view(state)


class OnboardError(ValueError):
    pass


def _advance(state: State, answer: str, probes: ProbeFns) -> State:
    step = state.step
    if step == "done":
        return state
    if not answer:
        raise OnboardError("Réponse vide. Envoie la valeur demandée.")

    if step == "odoo_url":
        url = answer.rstrip("/")
        if not url.startswith("https://") and not url.startswith("http://"):
            raise OnboardError("L'URL doit commencer par https://")
        state.draft["odoo_url"] = url
        state.step = "odoo_db"
        return state

    if step == "odoo_db":
        state.draft["odoo_db"] = answer
        state.step = "odoo_username"
        return state

    if step == "odoo_username":
        state.draft["odoo_username"] = answer
        state.step = "odoo_api_key"
        return state

    if step == "odoo_api_key":
        state.draft["odoo_api_key"] = answer
        cfg = _odoo_cfg(state)
        try:
            state.probe_odoo = probes.odoo(cfg)
        except Exception as exc:  # noqa: BLE001 — renvoyé au client
            raise OnboardError(f"Sonde Odoo échouée : {exc}") from exc
        state.step = "odoo_user"
        return state

    if step in {
        "odoo_user",
        "odoo_team",
        "odoo_stage",
        "odoo_project",
        "odoo_activity_call",
        "odoo_activity_todo",
    }:
        choices = _choices_for(state) or []
        if _is_skip(answer):
            if step in {"odoo_team", "odoo_project"} or not choices:
                state.draft[step] = None
                state.step = _next(step)
                return state
            raise OnboardError("Cette étape n'est pas optionnelle.")
        picked = _pick(answer, choices)
        state.draft[step] = int(picked.id)
        state.step = _next(step)
        return state

    if step == "ringover_key":
        state.draft["ringover_key"] = answer
        try:
            probes.ringover(RingoverConfig(api_key=answer))
        except Exception as exc:  # noqa: BLE001
            raise OnboardError(f"Sonde Ringover échouée : {exc}") from exc
        state.step = "imap_host"
        return state

    if step == "imap_host":
        state.draft["imap_host"] = answer
        state.step = "imap_user"
        return state

    if step == "imap_user":
        state.draft["imap_user"] = answer
        state.step = "imap_pass"
        return state

    if step == "imap_pass":
        state.draft["imap_pass"] = answer
        state.step = "imap_folder"
        return state

    if step == "imap_folder":
        folder = answer or "INBOX"
        state.draft["imap_folder"] = folder
        try:
            probes.imap(
                ImapConfig(
                    host=state.draft["imap_host"],
                    username=state.draft["imap_user"],
                    password=state.draft["imap_pass"],
                    folder=folder,
                )
            )
        except Exception as exc:  # noqa: BLE001
            raise OnboardError(f"Sonde IMAP échouée : {exc}") from exc
        state.step = "done"
        return state

    raise OnboardError(f"étape inconnue: {step}")


def _next(step: str) -> str:
    return STEPS[STEPS.index(step) + 1]


def _is_skip(answer: str) -> bool:
    return answer.lower() in {"skip", "passe", "-", "aucun", "none"}


def _pick(answer: str, choices: list[Choice]) -> Choice:
    if not choices:
        raise OnboardError("Aucun choix disponible — envoie skip.")
    if answer.isdigit():
        idx = int(answer)
        if 1 <= idx <= len(choices):
            return choices[idx - 1]
        raise OnboardError(f"Numéro hors liste (1–{len(choices)}).")
    by_id = [c for c in choices if c.id == answer]
    if len(by_id) == 1:
        return by_id[0]
    lowered = answer.lower()
    by_label = [c for c in choices if c.label.lower() == lowered]
    if len(by_label) == 1:
        return by_label[0]
    raise OnboardError("Réponds par le numéro de la liste.")


def _choices_for(state: State) -> list[Choice]:
    probe = state.probe_odoo or {}
    mapping = {
        "odoo_user": ("users", "name", "login"),
        "odoo_team": ("teams", "name", None),
        "odoo_stage": ("stages", "name", None),
        "odoo_project": ("projects", "name", None),
        "odoo_activity_call": ("activity_types", "name", "category"),
        "odoo_activity_todo": ("activity_types", "name", "category"),
    }
    spec = mapping.get(state.step)
    if not spec:
        return []
    key, label_k, extra = spec
    rows = probe.get(key) or []
    out: list[Choice] = []
    for row in rows:
        rid = row.get("id")
        if rid is None:
            continue
        label = str(row.get(label_k) or rid)
        if extra and row.get(extra):
            label = f"{label} ({row[extra]})"
        out.append(Choice(id=str(rid), label=label))
    return out


def _odoo_cfg(state: State) -> OdooConfig:
    return OdooConfig(
        url=state.draft["odoo_url"],
        db=state.draft["odoo_db"],
        username=state.draft["odoo_username"],
        api_key=state.draft["odoo_api_key"],
    )


def _persist_tenant(data_dir: Path, state: State) -> None:
    d = state.draft
    tenant = Tenant(
        timezone="Europe/Paris",
        odoo=OdooConfig(
            url=d["odoo_url"],
            db=d["odoo_db"],
            username=d["odoo_username"],
            api_key=d["odoo_api_key"],
            defaults=OdooDefaults(
                user_id=d.get("odoo_user"),
                team_id=d.get("odoo_team"),
                stage_id=d.get("odoo_stage"),
                project_id=d.get("odoo_project"),
                activity_type_call=d.get("odoo_activity_call"),
                activity_type_todo=d.get("odoo_activity_todo"),
            ),
        ),
        ringover=RingoverConfig(api_key=d["ringover_key"]),
        imap=ImapConfig(
            host=d["imap_host"],
            username=d["imap_user"],
            password=d["imap_pass"],
            folder=d.get("imap_folder") or "INBOX",
        ),
    )
    save_tenant(data_dir, tenant)
