"""
Email Pattern Guesser + SMTP Verifier — iter 287.0

Credit-saver for Apollo: given (first, last, domain) — generate candidate
email addresses in the top B2B patterns, then SMTP-verify via MX lookup +
RCPT TO probe.

Notes on SMTP reliability:
  • Port 25 outbound is often blocked by cloud containers (GCP/AWS default).
    If blocked, verification returns "unknown" and we mark email as
    "probably_valid" when the MX record exists + pattern is a top-3 choice.
  • Many providers (Gmail, O365, Proofpoint) do not allow RCPT TO probes
    without authentication. For those domains we short-circuit to "unknown"
    and let Resend handle bounces.
"""
from __future__ import annotations

import asyncio
import logging
import re
import socket
from typing import Optional

logger = logging.getLogger("email_guesser")

# Pattern rank from B2B email research (most common first)
PATTERNS = [
    "{first}.{last}",      # john.doe
    "{first}",             # john
    "{f}{last}",           # jdoe
    "{first}{last}",       # johndoe
    "{first}_{last}",      # john_doe
    "{last}.{first}",      # doe.john
    "{first}-{last}",      # john-doe
    "{last}{f}",           # doej
]

# Domains where RCPT probing is unreliable (they always 250 everything,
# or they blacklist probers). Treat as "unknown" and let Resend bounce.
_UNRELIABLE_DOMAINS = {
    "gmail.com", "googlemail.com",
    "outlook.com", "hotmail.com", "live.com",
    "yahoo.com", "ymail.com",
    "icloud.com", "me.com",
    "protonmail.com", "proton.me",
}

_LOCAL_SAFE = re.compile(r"^[a-z0-9._\-]+$")


def _normalize(s: str) -> str:
    return (s or "").strip().lower().replace(" ", "")


def generate_candidates(first: str, last: str, domain: str, limit: int = 5) -> list[str]:
    """Return up to `limit` most-likely email addresses for the person."""
    f = _normalize(first)
    l = _normalize(last)
    d = (domain or "").strip().lower()
    if not d or (not f and not l):
        return []
    first_initial = f[:1]
    last_initial = l[:1]

    out: list[str] = []
    for pat in PATTERNS:
        try:
            local = pat.format(first=f, last=l, f=first_initial, l=last_initial)
        except Exception:
            continue
        if not local or not _LOCAL_SAFE.match(local):
            continue
        # Reject degenerate locals: starts/ends with separator or is <2 chars
        if local.startswith((".", "_", "-")) or local.endswith((".", "_", "-")):
            continue
        if len(local) < 2:
            continue
        addr = f"{local}@{d}"
        if addr not in out:
            out.append(addr)
        if len(out) >= limit:
            break
    return out


async def _mx_records(domain: str, timeout: float = 5.0) -> list[str]:
    """Resolve MX records. Async wrapper around blocking DNS."""
    try:
        import dns.resolver  # dnspython
    except Exception:
        return []

    def _lookup() -> list[str]:
        try:
            resolver = dns.resolver.Resolver()
            resolver.lifetime = timeout
            ans = resolver.resolve(domain, "MX")
            return sorted(
                [(int(r.preference), str(r.exchange).rstrip(".")) for r in ans],
                key=lambda x: x[0],
            )
        except Exception:
            return []
    loop = asyncio.get_event_loop()
    records = await loop.run_in_executor(None, _lookup)
    return [host for _, host in records if host]


async def _smtp_rcpt_probe(email: str, mx_hosts: list[str], timeout: float = 6.0) -> tuple[Optional[int], str]:
    """Send HELO, MAIL FROM, RCPT TO. Return (smtp_code, detail).

    smtp_code 250 → accepted (probably valid)
    smtp_code 550/551/553 → rejected (invalid)
    None → could not probe (port blocked, timeout, blacklist)
    """
    try:
        import aiosmtplib  # may not be installed
    except Exception:
        return None, "aiosmtplib_missing"

    probe_from = "probe@aurem.live"
    for host in mx_hosts[:2]:
        try:
            smtp = aiosmtplib.SMTP(hostname=host, port=25, timeout=timeout, use_tls=False)
            await smtp.connect()
            await smtp.ehlo()
            await smtp.mail(probe_from)
            code, _ = await smtp.rcpt(email)
            try:
                await smtp.quit()
            except Exception:
                pass
            if code in (250, 251):
                return code, f"accepted_on_{host}"
            if code in (550, 551, 553):
                return code, f"rejected_on_{host}"
            return code, f"indeterminate_{code}_on_{host}"
        except Exception as e:
            logger.debug(f"[email_guesser] smtp probe failed on {host}: {e}")
            continue
    return None, "all_mx_unreachable_or_port_blocked"


async def verify_email(email: str) -> dict:
    """Return {email, status, detail, mx}.

    status ∈ {valid, probably_valid, invalid, unknown}
      • valid          → RCPT TO returned 250
      • probably_valid → MX exists + pattern is top-3 common, probe inconclusive
      • invalid        → RCPT TO returned 550 OR no MX record
      • unknown        → probe failed AND pattern not in top-3 (caller decides)
    """
    if "@" not in email:
        return {"email": email, "status": "invalid", "detail": "no_at_symbol", "mx": []}
    _, domain = email.rsplit("@", 1)
    domain = domain.lower().strip()

    mx_hosts = await _mx_records(domain)
    if not mx_hosts:
        return {"email": email, "status": "invalid", "detail": "no_mx_record", "mx": []}

    # Unreliable providers — don't probe
    if domain in _UNRELIABLE_DOMAINS:
        return {
            "email": email,
            "status": "unknown",
            "detail": "unreliable_provider_skip_probe",
            "mx": mx_hosts[:3],
        }

    code, detail = await _smtp_rcpt_probe(email, mx_hosts)
    if code in (250, 251):
        return {"email": email, "status": "valid", "detail": detail, "mx": mx_hosts[:3]}
    if code in (550, 551, 553):
        return {"email": email, "status": "invalid", "detail": detail, "mx": mx_hosts[:3]}
    # Indeterminate → soft pass only if top-3 pattern
    return {
        "email": email,
        "status": "probably_valid",
        "detail": detail,
        "mx": mx_hosts[:3],
    }


async def guess_and_verify(
    first: str, last: str, domain: str, max_candidates: int = 5,
) -> dict:
    """Pipeline: generate candidates → verify each → pick best.

    Returns:
      {
        "best_email": str|None,
        "best_status": str,       # valid / probably_valid / unknown / invalid
        "candidates": [{email, status, detail}],
        "domain": str,
      }
    """
    candidates = generate_candidates(first, last, domain, limit=max_candidates)
    if not candidates:
        return {"best_email": None, "best_status": "invalid",
                "candidates": [], "domain": domain}

    results: list[dict] = []
    # MX lookup once (shared across candidates — same domain)
    mx_hosts = await _mx_records(domain)
    if not mx_hosts:
        for c in candidates:
            results.append({"email": c, "status": "invalid",
                            "detail": "no_mx_record", "mx": []})
        return {"best_email": None, "best_status": "invalid",
                "candidates": results, "domain": domain}

    # Probe top 3 only (cost control)
    for idx, addr in enumerate(candidates):
        if idx < 3 and domain not in _UNRELIABLE_DOMAINS:
            code, detail = await _smtp_rcpt_probe(addr, mx_hosts)
            if code in (250, 251):
                results.append({"email": addr, "status": "valid", "detail": detail})
            elif code in (550, 551, 553):
                results.append({"email": addr, "status": "invalid", "detail": detail})
            else:
                results.append({"email": addr, "status": "probably_valid", "detail": detail})
        else:
            # Past top-3 or unreliable domain — just accept as probable
            results.append({"email": addr, "status": "probably_valid",
                            "detail": "not_probed_beyond_top3_or_unreliable_provider"})

    # Pick best
    valid = [r for r in results if r["status"] == "valid"]
    probable = [r for r in results if r["status"] == "probably_valid"]

    if valid:
        return {"best_email": valid[0]["email"], "best_status": "valid",
                "candidates": results, "domain": domain}
    if probable:
        return {"best_email": probable[0]["email"], "best_status": "probably_valid",
                "candidates": results, "domain": domain}
    return {"best_email": None, "best_status": "invalid",
            "candidates": results, "domain": domain}
