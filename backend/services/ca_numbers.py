"""
iter 282al-33 — Canadian NPA (area code) allowlist for SMS kill-switch.

Canada follows CRTC CASL rules, not US A2P 10DLC. Twilio does NOT block
SMS delivery from a CA long code to CA numbers with error 30034 — that
error is scoped to US destinations. So we safely allow CA→CA traffic
today while the US A2P 10DLC campaign is in registration.

Source: Canadian Numbering Administration (CNA).
Last refreshed: 2026-02.
"""
from __future__ import annotations

import re

# Active + announced Canadian NPAs (area codes). Kept flat for O(1) lookup.
CA_NPAS = frozenset({
    "204", "226", "236", "249", "250", "263", "289", "306", "343", "354",
    "365", "367", "368", "382", "403", "416", "418", "428", "431", "437",
    "438", "450", "468", "474", "506", "514", "519", "548", "579", "581",
    "584", "587", "600", "604", "613", "639", "647", "672", "683", "705",
    "709", "742", "753", "778", "780", "782", "807", "819", "825", "867",
    "873", "879", "902", "905",
})

_E164_RE = re.compile(r"^\+?1?(\d{3})\d{7}$")


def is_canadian_number(phone: str) -> bool:
    """True iff phone is E.164 NANP with a Canadian NPA."""
    if not phone:
        return False
    # Strip anything non-digit except leading +
    digits = re.sub(r"[^\d]", "", str(phone))
    if digits.startswith("1") and len(digits) == 11:
        npa = digits[1:4]
    elif len(digits) == 10:
        npa = digits[:3]
    else:
        return False
    return npa in CA_NPAS


def is_us_number(phone: str) -> bool:
    """Best-effort: NANP number that is NOT in the CA allowlist = US.

    Note: Caribbean NANP NPAs (242/441/473/etc.) also fall here, but that's
    fine — they are also subject to carrier policies and we prefer the safe
    default of blocking until policy is confirmed.
    """
    if not phone:
        return False
    digits = re.sub(r"[^\d]", "", str(phone))
    if digits.startswith("1") and len(digits) == 11:
        npa = digits[1:4]
    elif len(digits) == 10:
        npa = digits[:3]
    else:
        return False
    return npa not in CA_NPAS
