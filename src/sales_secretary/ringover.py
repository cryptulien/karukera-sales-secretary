"""Client Ringover : liste des appels + transcription Empower."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from sales_secretary.phones import normalize_phone
from sales_secretary.schemas import EventRecord, utcnow_iso
from sales_secretary.tenant import RingoverConfig


class RingoverError(RuntimeError):
    pass


class RingoverClient:
    def __init__(self, cfg: RingoverConfig, timeout: float = 30.0) -> None:
        self.cfg = cfg
        self._http = httpx.Client(
            base_url=cfg.base_url.rstrip("/"),
            headers={"Authorization": cfg.api_key, "Accept": "application/json"},
            timeout=timeout,
        )

    def close(self) -> None:
        self._http.close()

    def ping(self) -> dict[str, Any]:
        """Sonde minimale : 1 page d'appels."""
        calls = self.list_calls(limit=1)
        return {"ok": True, "sample": len(calls)}

    def list_calls(
        self,
        *,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit_count": limit}
        if since is not None:
            params["start_date"] = since.astimezone(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.00Z"
            )
        response = self._http.get("/calls", params=params)
        if response.status_code == 405:
            response = self._http.post("/calls", json=params)
        if response.status_code >= 400:
            raise RingoverError(
                f"Ringover {response.status_code}: {response.text[:400]}"
            )
        data = response.json()
        return _extract_call_list(data)

    def call_detail(self, call_id: str) -> dict[str, Any]:
        response = self._http.get(f"/calls/{call_id}")
        if response.status_code >= 400:
            return {}
        payload = response.json()
        if isinstance(payload, dict) and "call" in payload:
            return payload["call"] if isinstance(payload["call"], dict) else payload
        return payload if isinstance(payload, dict) else {}

    def empower_bundle(self, call_uuid: str) -> dict[str, Any]:
        """Transcription + résumé Empower. Tolère l'absence d'option Empower."""
        out: dict[str, Any] = {}
        for suffix, key in (
            (f"/public/empower/call/{call_uuid}", "transcription"),
            (f"/public/empower/call/{call_uuid}/summary", "summary"),
        ):
            try:
                response = self._http.get(suffix)
            except httpx.HTTPError:
                continue
            if response.status_code >= 400:
                continue
            try:
                out[key] = response.json()
            except ValueError:
                out[key] = response.text
        return out

    def harvest(self, lookback_hours: int = 48, limit: int = 50) -> list[EventRecord]:
        since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        calls = self.list_calls(since=since, limit=limit)
        events: list[EventRecord] = []
        for raw in calls:
            enriched = dict(raw)
            call_id = _call_id(raw)
            if not call_id:
                continue
            detail = self.call_detail(str(call_id))
            if detail:
                enriched.update(detail)
            uuid = _call_uuid(enriched)
            if uuid:
                empower = self.empower_bundle(str(uuid))
                if empower:
                    enriched["empower"] = empower
            events.append(call_to_event(enriched))
        return events


def _extract_call_list(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [c for c in data if isinstance(c, dict)]
    if not isinstance(data, dict):
        return []
    for key in ("call_list", "calls", "list", "items"):
        value = data.get(key)
        if isinstance(value, list):
            return [c for c in value if isinstance(c, dict)]
    return []


def _call_id(raw: dict[str, Any]) -> str | None:
    for key in ("call_id", "id", "cdr_id"):
        if raw.get(key) is not None:
            return str(raw[key])
    return None


def _call_uuid(raw: dict[str, Any]) -> str | None:
    for key in ("call_uuid", "uuid", "platform_id", "calluuid"):
        if raw.get(key):
            return str(raw[key])
    channel = raw.get("channel")
    if isinstance(channel, dict) and channel.get("uuid"):
        return str(channel["uuid"])
    return _call_id(raw)


def _first_text(*candidates: Any) -> str:
    for item in candidates:
        if isinstance(item, str) and item.strip():
            return item.strip()
        if isinstance(item, dict):
            for key in ("text", "transcript", "content", "summary", "value"):
                if isinstance(item.get(key), str) and item[key].strip():
                    return item[key].strip()
            parts = item.get("utterances") or item.get("segments")
            if isinstance(parts, list):
                lines = []
                for part in parts:
                    if isinstance(part, dict):
                        speaker = part.get("speaker") or part.get("who") or ""
                        text = part.get("text") or part.get("content") or ""
                        if text:
                            lines.append(f"{speaker}: {text}".strip(": "))
                    elif isinstance(part, str):
                        lines.append(part)
                if lines:
                    return "\n".join(lines)
    return ""


def extract_transcript(raw: dict[str, Any]) -> str:
    empower = raw.get("empower") if isinstance(raw.get("empower"), dict) else {}
    return _first_text(
        raw.get("transcription"),
        raw.get("transcript"),
        raw.get("note"),
        raw.get("notes"),
        empower.get("transcription") if isinstance(empower, dict) else None,
        empower.get("summary") if isinstance(empower, dict) else None,
        raw.get("last_state"),
    )


def extract_summary(raw: dict[str, Any]) -> str:
    empower = raw.get("empower") if isinstance(raw.get("empower"), dict) else {}
    return _first_text(
        empower.get("summary") if isinstance(empower, dict) else None,
        raw.get("summary"),
        raw.get("ivr_name"),
    )


def counterpart_number(raw: dict[str, Any]) -> str | None:
    for key in (
        "from_number",
        "to_number",
        "contact_number",
        "number",
        "caller_id",
        "clir_number",
    ):
        value = raw.get(key)
        if value:
            # Un appel sortant : le correspondant est to_number.
            direction = str(raw.get("direction") or raw.get("type") or "").lower()
            if key == "from_number" and direction in {"out", "outbound", "sortant"}:
                continue
            if key == "to_number" and direction in {"in", "inbound", "entrant"}:
                continue
            return normalize_phone(str(value))
    numbers = raw.get("numbers")
    if isinstance(numbers, dict):
        for key in ("contact", "from", "to"):
            if numbers.get(key):
                return normalize_phone(str(numbers[key]))
    return normalize_phone(str(raw.get("from_number") or raw.get("to_number") or ""))


def call_to_event(raw: dict[str, Any]) -> EventRecord:
    call_id = _call_id(raw) or "unknown"
    occurred = (
        raw.get("start_time")
        or raw.get("date")
        or raw.get("started_at")
        or raw.get("creation_date")
        or utcnow_iso()
    )
    if isinstance(occurred, (int, float)):
        occurred = datetime.fromtimestamp(int(occurred), tz=timezone.utc).isoformat()
    now = utcnow_iso()
    contact = raw.get("contact")
    contact_name = raw.get("contact_name") or (
        contact.get("name") if isinstance(contact, dict) else None
    )
    payload = {
        "call_id": call_id,
        "direction": raw.get("direction") or raw.get("type"),
        "duration": raw.get("total_duration") or raw.get("duration") or 0,
        "answered": bool(raw.get("answered", raw.get("is_answered", True))),
        "phone": counterpart_number(raw),
        "contact_name": contact_name or "",
        "user": raw.get("user_name") or raw.get("user"),
        "transcript": extract_transcript(raw),
        "summary": extract_summary(raw),
        "raw_keys": sorted(raw.keys()),
    }
    return EventRecord(
        id=f"ringover:call:{call_id}",
        source="ringover",
        external_id=str(call_id),
        kind="call",
        occurred_at=str(occurred),
        payload=payload,
        status="new",
        created_at=now,
        updated_at=now,
    )
