"""
Phone number normalization for WhatsApp / SMS dispatchers.

Why this exists (iter 323d):
  The campaign engine was dispatching messages with raw `lead["phone"]`
  values that contained letters ("ext"), dots, unicode, or empty strings.
  WHAPI rejected them with:
    /body/to must match pattern "^[\d-]{9,31}(@[\w\.]{1,})?$"
  Twilio rejected non-E.164 inputs.

Two normalizers:
  - to_whapi_format(phone)  — digits-only, 9–31 chars, returns "" on invalid
  - to_e164(phone, default_country="1") — E.164 (+15551234567), used by Twilio
"""

from __future__ import annotations

import re
from typing import Optional

_DIGITS = re.compile(r"\D+")  # everything that is NOT a digit


def to_whapi_format(phone: object) -> str:
    """
    Strip every non-digit character and return the result IFF it is
    a plausible international subscriber number (9–15 digits).
    Returns "" when input is empty / invalid.
    """
    if not phone:
        return ""
    raw = str(phone).strip()
    if not raw:
        return ""
    digits = _DIGITS.sub("", raw)
    # WHAPI allows 9–31 chars; real phone numbers are 9–15 digits
    if not (9 <= len(digits) <= 15):
        return ""
    return digits


def to_e164(phone: object, default_country: str = "1") -> str:
    """
    Return phone in E.164 format (e.g. +15551234567) for Twilio.
    Falls back to default_country code if the number is 10 digits and
    looks like a North-American local number.
    Returns "" on invalid input.
    """
    digits = to_whapi_format(phone)
    if not digits:
        return ""
    # If user already prefixed `+`, honour their country code.
    raw = str(phone).strip()
    if raw.startswith("+"):
        return "+" + digits
    # 10 digits → assume NANP (US/CA)
    if len(digits) == 10 and default_country in ("1",):
        return f"+{default_country}{digits}"
    return f"+{digits}"


def is_valid_phone(phone: object) -> bool:
    """Quick check: does this look like a sendable phone number?"""
    return bool(to_whapi_format(phone))


__all__ = ["to_whapi_format", "to_e164", "is_valid_phone"]
