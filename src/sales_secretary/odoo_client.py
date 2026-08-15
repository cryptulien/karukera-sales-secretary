"""Client JSON-RPC Odoo (16–19)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import httpx

from sales_secretary.tenant import OdooConfig


class OdooError(RuntimeError):
    pass


class OdooClient:
    def __init__(self, cfg: OdooConfig, timeout: float = 30.0) -> None:
        self.cfg = cfg
        self._http = httpx.Client(timeout=timeout)
        self._uid: int | None = None
        self._endpoint = urljoin(cfg.url.rstrip("/") + "/", "jsonrpc")

    def close(self) -> None:
        self._http.close()

    def authenticate(self) -> int:
        if self._uid is not None:
            return self._uid
        uid = self._call("common", "authenticate", [self.cfg.db, self.cfg.username, self.cfg.api_key, {}])
        if not uid:
            raise OdooError("authentification Odoo refusée")
        self._uid = int(uid)
        return self._uid

    def execute_kw(
        self,
        model: str,
        method: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        uid = self.authenticate()
        return self._call(
            "object",
            "execute_kw",
            [self.cfg.db, uid, self.cfg.api_key, model, method, args or [], kwargs or {}],
        )

    def search_read(
        self,
        model: str,
        domain: list[Any],
        fields: list[str],
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        result = self.execute_kw(
            model,
            "search_read",
            [domain],
            {"fields": fields, "limit": limit},
        )
        return result or []

    def create(self, model: str, vals: dict[str, Any]) -> int:
        return int(self.execute_kw(model, "create", [vals]))

    def write(self, model: str, ids: list[int], vals: dict[str, Any]) -> bool:
        return bool(self.execute_kw(model, "write", [ids, vals]))

    def fields_get(self, model: str, attributes: list[str] | None = None) -> dict[str, Any]:
        return self.execute_kw(model, "fields_get", [], {"attributes": attributes or ["string", "type"]})

    def probe(self) -> dict[str, Any]:
        """Liste ce dont l'onboarding a besoin pour remplir tenant.yaml."""
        uid = self.authenticate()
        users = self.search_read(
            "res.users",
            [("share", "=", False), ("active", "=", True)],
            ["name", "login"],
            limit=40,
        )
        teams = _safe_search(self, "crm.team", [], ["name"], 20)
        stages = _safe_search(self, "crm.stage", [], ["name", "team_id"], 40)
        projects = _safe_search(self, "project.project", [("active", "=", True)], ["name"], 40)
        activity_types = _safe_search(self, "mail.activity.type", [], ["name", "category"], 40)
        return {
            "ok": True,
            "uid": uid,
            "db": self.cfg.db,
            "url": self.cfg.url,
            "users": users,
            "teams": teams,
            "stages": stages,
            "projects": projects,
            "activity_types": activity_types,
        }

    def _call(self, service: str, method: str, args: list[Any]) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {"service": service, "method": method, "args": args},
            "id": 1,
        }
        response = self._http.post(self._endpoint, json=payload)
        if response.status_code >= 400:
            raise OdooError(f"HTTP {response.status_code}: {response.text[:300]}")
        body = response.json()
        if body.get("error"):
            err = body["error"]
            data = err.get("data") or {}
            raise OdooError(data.get("message") or err.get("message") or str(err))
        return body.get("result")


def _safe_search(
    client: OdooClient,
    model: str,
    domain: list[Any],
    fields: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    try:
        return client.search_read(model, domain, fields, limit=limit)
    except OdooError:
        return []
