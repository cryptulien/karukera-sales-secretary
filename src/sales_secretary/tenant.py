"""Lecture / écriture du tenant.yaml (secrets métier)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class OdooDefaults(BaseModel):
    team_id: int | None = None
    stage_id: int | None = None
    user_id: int | None = None
    project_id: int | None = None
    activity_type_call: int | None = None
    activity_type_email: int | None = None
    activity_type_todo: int | None = None
    email_from: str | None = None


class OdooConfig(BaseModel):
    url: str
    db: str
    username: str
    api_key: str
    defaults: OdooDefaults = Field(default_factory=OdooDefaults)


class RingoverConfig(BaseModel):
    api_key: str
    base_url: str = "https://public-api.ringover.com/v2"


class ImapConfig(BaseModel):
    host: str
    username: str
    password: str
    port: int = 993
    folder: str = "INBOX"
    use_ssl: bool = True


class PollConfig(BaseModel):
    interval_seconds: int = 180
    lookback_hours: int = 48


class Tenant(BaseModel):
    timezone: str = "Europe/Paris"
    odoo: OdooConfig | None = None
    ringover: RingoverConfig | None = None
    imap: ImapConfig | None = None
    poll: PollConfig = Field(default_factory=PollConfig)

    def configured(self) -> bool:
        return self.odoo is not None and (
            self.ringover is not None or self.imap is not None
        )


def tenant_path(data_dir: Path) -> Path:
    return data_dir / "tenant.yaml"


def load_tenant(data_dir: Path) -> Tenant | None:
    path = tenant_path(data_dir)
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Tenant.model_validate(raw)


def save_tenant(data_dir: Path, tenant: Tenant) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    path = tenant_path(data_dir)
    payload: dict[str, Any] = tenant.model_dump(exclude_none=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


def public_tenant(tenant: Tenant | None) -> dict[str, Any]:
    """Vue sans secrets, pour GET /status."""
    if tenant is None:
        return {"configured": False}
    return {
        "configured": tenant.configured(),
        "timezone": tenant.timezone,
        "odoo": bool(tenant.odoo),
        "ringover": bool(tenant.ringover),
        "imap": bool(tenant.imap),
        "odoo_url": tenant.odoo.url if tenant.odoo else None,
        "imap_host": tenant.imap.host if tenant.imap else None,
        "defaults": tenant.odoo.defaults.model_dump() if tenant.odoo else {},
        "poll": tenant.poll.model_dump(),
    }
