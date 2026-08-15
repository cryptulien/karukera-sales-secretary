"""Normalisation de numéros, prioritairement France."""

from __future__ import annotations

import re


_NON_DIGIT = re.compile(r"[^\d+]")


def normalize_phone(raw: str | None, default_region: str = "FR") -> str | None:
    """Retourne un E.164 (+33…) ou None si inexploitable."""
    if not raw:
        return None
    text = _NON_DIGIT.sub("", str(raw).strip())
    if not text:
        return None

    if text.startswith("00"):
        text = "+" + text[2:]

    if default_region == "FR":
        if text.startswith("0") and len(text) == 10:
            return "+33" + text[1:]
        if text.isdigit() and len(text) == 9 and text[0] in "16789":
            return "+33" + text
        if text.startswith("+33") and len(re.sub(r"\D", "", text)) >= 11:
            digits = re.sub(r"\D", "", text)
            return "+" + digits
        if text.startswith("+") and len(re.sub(r"\D", "", text)) >= 8:
            return "+" + re.sub(r"\D", "", text)
        return None

    if text.startswith("+"):
        return "+" + re.sub(r"\D", "", text)
    digits = re.sub(r"\D", "", text)
    return digits or None


def phone_search_tail(e164: str | None, length: int = 9) -> str | None:
    """Derniers chiffres pour un `ilike` Odoo (ignore indicatif)."""
    if not e164:
        return None
    digits = re.sub(r"\D", "", e164)
    if len(digits) < 6:
        return None
    return digits[-length:]
