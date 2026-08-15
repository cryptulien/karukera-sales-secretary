"""Poll IMAP : un événement par UID, corps texte seulement."""

from __future__ import annotations

import email
import imaplib
import re
from email.header import decode_header
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime
from typing import Any, Callable

from sales_secretary.schemas import EventRecord, utcnow_iso
from sales_secretary.tenant import ImapConfig


ImapFactory = Callable[[ImapConfig], Any]


class ImapError(RuntimeError):
    pass


def connect_imap(cfg: ImapConfig) -> imaplib.IMAP4:
    if cfg.use_ssl:
        client = imaplib.IMAP4_SSL(cfg.host, cfg.port)
    else:
        client = imaplib.IMAP4(cfg.host, cfg.port)
    typ, _ = client.login(cfg.username, cfg.password)
    if typ != "OK":
        raise ImapError(f"IMAP login failed: {typ}")
    return client


def ping_imap(cfg: ImapConfig, factory: ImapFactory = connect_imap) -> dict[str, Any]:
    client = factory(cfg)
    try:
        typ, _ = client.select(cfg.folder, readonly=True)
        if typ != "OK":
            raise ImapError(f"IMAP select {cfg.folder}: {typ}")
        return {"ok": True, "folder": cfg.folder}
    finally:
        try:
            client.logout()
        except Exception:
            pass


def harvest_imap(
    cfg: ImapConfig,
    *,
    limit: int = 30,
    factory: ImapFactory = connect_imap,
) -> list[EventRecord]:
    client = factory(cfg)
    try:
        typ, _ = client.select(cfg.folder, readonly=True)
        if typ != "OK":
            raise ImapError(f"IMAP select {cfg.folder}: {typ}")
        status, data = client.uid("search", None, "ALL")
        if status != "OK":
            raise ImapError(f"IMAP search: {status}")
        uids = (data[0] or b"").split()
        uids = uids[-limit:]
        uidvalidity = _uidvalidity(client, cfg.folder)
        events: list[EventRecord] = []
        for uid in uids:
            fetched = client.uid("fetch", uid, "(RFC822)")
            if fetched[0] != "OK" or not fetched[1]:
                continue
            raw = _extract_rfc822(fetched[1])
            if raw is None:
                continue
            events.append(
                message_to_event(
                    raw,
                    folder=cfg.folder,
                    uidvalidity=uidvalidity,
                    uid=uid.decode() if isinstance(uid, bytes) else str(uid),
                )
            )
        return events
    finally:
        try:
            client.logout()
        except Exception:
            pass


def message_to_event(
    raw: bytes,
    *,
    folder: str,
    uidvalidity: str,
    uid: str,
) -> EventRecord:
    msg = email.message_from_bytes(raw)
    message_id = (msg.get("Message-ID") or msg.get("Message-Id") or uid).strip()
    subject = _decode_header(msg.get("Subject"))
    from_name, from_email = parseaddr(msg.get("From", ""))
    occurred = _message_date(msg)
    now = utcnow_iso()
    body = _plain_body(msg)
    payload = {
        "message_id": message_id,
        "subject": subject,
        "from_name": from_name,
        "from_email": from_email.lower() if from_email else "",
        "to": msg.get("To", ""),
        "body": body[:20000],
    }
    return EventRecord(
        id=f"imap:{folder}:{uidvalidity}:{uid}",
        source="imap",
        external_id=f"{uidvalidity}:{uid}",
        kind="email",
        occurred_at=occurred,
        payload=payload,
        status="new",
        created_at=now,
        updated_at=now,
    )


def _uidvalidity(client: Any, folder: str) -> str:
    typ, data = client.status(folder, "(UIDVALIDITY)")
    if typ != "OK" or not data:
        return "0"
    text = data[0].decode() if isinstance(data[0], bytes) else str(data[0])
    match = re.search(r"UIDVALIDITY\s+(\d+)", text)
    return match.group(1) if match else "0"


def _extract_rfc822(fetch_data: Any) -> bytes | None:
    for part in fetch_data:
        if isinstance(part, tuple) and len(part) >= 2 and isinstance(part[1], bytes):
            return part[1]
    return None


def _decode_header(value: str | None) -> str:
    if not value:
        return ""
    chunks = []
    for text, charset in decode_header(value):
        if isinstance(text, bytes):
            chunks.append(text.decode(charset or "utf-8", errors="replace"))
        else:
            chunks.append(text)
    return "".join(chunks).strip()


def _message_date(msg: Message) -> str:
    raw = msg.get("Date")
    if not raw:
        return utcnow_iso()
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            return dt.isoformat() + "+00:00"
        return dt.isoformat()
    except (TypeError, ValueError, IndexError):
        return utcnow_iso()


def _plain_body(msg: Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace").strip()
        for part in msg.walk():
            if part.get_content_type() == "text/html" and not part.get_filename():
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                return _strip_html(payload.decode(charset, errors="replace"))
        return ""
    payload = msg.get_payload(decode=True) or b""
    charset = msg.get_content_charset() or "utf-8"
    text = payload.decode(charset, errors="replace")
    if msg.get_content_type() == "text/html":
        return _strip_html(text)
    return text.strip()


def _strip_html(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()
