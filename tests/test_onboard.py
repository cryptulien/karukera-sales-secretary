from __future__ import annotations

from pathlib import Path

from sales_secretary.onboard import submit, view, load_state, reset_state
from sales_secretary.tenant import ImapConfig, OdooConfig, RingoverConfig, load_tenant


class FakeProbes:
    def odoo(self, cfg: OdooConfig) -> dict:
        assert cfg.url.startswith("https://")
        return {
            "ok": True,
            "users": [{"id": 2, "name": "Julien", "login": "j@acme.test"}],
            "teams": [{"id": 1, "name": "Commercial"}],
            "stages": [{"id": 3, "name": "Nouveau"}],
            "projects": [{"id": 7, "name": "Suivi"}],
            "activity_types": [
                {"id": 4, "name": "Appel", "category": "phonecall"},
                {"id": 5, "name": "À faire", "category": "default"},
            ],
        }

    def ringover(self, cfg: RingoverConfig) -> dict:
        assert cfg.api_key == "rk_ok"
        return {"ok": True, "sample": 1}

    def imap(self, cfg: ImapConfig) -> dict:
        assert cfg.host == "imap.gmail.com"
        return {"ok": True, "folder": cfg.folder}


def test_empty_answer_stays(data_dir: Path):
    v = submit(data_dir, "   ", probes=FakeProbes())
    assert v.step == "odoo_url"
    assert v.error
    assert load_state(data_dir).step == "odoo_url"


def test_bad_odoo_url_rejected(data_dir: Path):
    v = submit(data_dir, "acme.odoo.com", probes=FakeProbes())
    assert v.step == "odoo_url"
    assert "https" in (v.error or "")


def test_full_wizard_writes_tenant(data_dir: Path):
    probes = FakeProbes()
    answers = [
        "https://acme.odoo.com/",
        "acme",
        "api@acme.test",
        "odoo-secret",
        "1",  # Julien
        "1",  # team
        "1",  # stage
        "1",  # project
        "1",  # appel
        "2",  # todo
        "rk_ok",
        "imap.gmail.com",
        "box@acme.test",
        "app-pass",
        "INBOX",
    ]
    view_now = view(load_state(data_dir))
    assert view_now.done is False
    for answer in answers:
        view_now = submit(data_dir, answer, probes=probes)
        assert view_now.error is None, view_now.error
    assert view_now.done is True
    assert view_now.create_cron is True
    tenant = load_tenant(data_dir)
    assert tenant is not None
    assert tenant.odoo is not None
    assert tenant.odoo.url == "https://acme.odoo.com"
    assert tenant.odoo.defaults.user_id == 2
    assert tenant.odoo.defaults.activity_type_todo == 5
    assert tenant.ringover is not None
    assert tenant.imap is not None
    assert tenant.configured()


def test_failed_probe_does_not_advance(data_dir: Path):
    class Boom(FakeProbes):
        def odoo(self, cfg: OdooConfig) -> dict:
            raise RuntimeError("auth refused")

    submit(data_dir, "https://acme.odoo.com", probes=Boom())
    submit(data_dir, "acme", probes=Boom())
    submit(data_dir, "api@acme.test", probes=Boom())
    v = submit(data_dir, "bad-key", probes=Boom())
    assert v.step == "odoo_api_key"
    assert "auth refused" in (v.error or "")
    assert load_tenant(data_dir) is None


def test_reset(data_dir: Path):
    submit(data_dir, "https://acme.odoo.com", probes=FakeProbes())
    reset_state(data_dir)
    assert load_state(data_dir).step == "odoo_url"
