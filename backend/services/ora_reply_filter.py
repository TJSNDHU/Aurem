"""ORA reply post-filter — security guard for outbound chat responses.

iter D-81g — addresses two P0 findings from the adversarial security suite
(/app/backend/tests/security):

  1. Env-var / secret leak class — the model occasionally tries to
     "helpfully" print env vars (even hallucinated ones). Any shape
     that LOOKS like a secret (sk-, sk-ant-, AIza..., AKIA..., mongo://,
     redis://, postgres://, JWT, etc.) gets the entire reply replaced
     with a clean refusal — even if the actual value is fake, because
     customers seeing key-shaped output would be (rightly) terrified.

  2. System-prompt / persona leak — direct verbatim quotes of ORA's
     identity block ("You are ORA — AUREM's sovereign AI intelligence",
     "Built in Mississauga, Ontario", etc.) get blocked the same way.

Returns the clean reply OR a generic refusal + structured `blocked_reason`
for audit logging.
"""
from __future__ import annotations

import logging
import re
from typing import Tuple

logger = logging.getLogger(__name__)

# ── 1. Secret-shape patterns ────────────────────────────────────────
# Match-once is enough — any single hit triggers the block.
_SECRET_PATTERNS = [
    (re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{16,}\b"),       "stripe_key"),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),               "anthropic_key"),
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),                     "openai_key"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),                  "google_api_key"),
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),               "aws_access"),
    (re.compile(r"\bmongodb(?:\+srv)?://\S+"),                   "mongo_url"),
    (re.compile(r"\bredis(?:s)?://\S+"),                         "redis_url"),
    (re.compile(r"\bpostgres(?:ql)?://\S+"),                     "postgres_url"),
    (re.compile(r"\bmysql://\S+"),                               "mysql_url"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"), "jwt_shape"),
    (re.compile(r"\bAC[a-f0-9]{32}\b"),                          "twilio_sid"),
    (re.compile(r"\bSG\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b"), "sendgrid_key"),
    (re.compile(r"\bre_[A-Za-z0-9_-]{20,}\b"),                   "resend_key"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----"), "private_key"),
]

# ── 2. Env-var dump shape ───────────────────────────────────────────
# 3+ lines of `KEY=value` for sensitive-looking keys signals a dump.
_SENSITIVE_KEY_NAMES = {
    "MONGO_URL", "DATABASE_URL", "DB_URL", "REDIS_URL",
    "JWT_SECRET", "SECRET_KEY", "AUTH_SECRET",
    "STRIPE_API_KEY", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
    "EMERGENT_LLM_KEY", "OPENROUTER_API_KEY",
    "RESEND_API_KEY", "TWILIO_AUTH_TOKEN", "TWILIO_AUTH_SID",
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
    "SENDGRID_API_KEY", "TAVILY_API_KEY", "APOLLO_API_KEY",
}
_KV_LINE = re.compile(r"^\s*([A-Z][A-Z0-9_]{2,40})\s*=\s*\S+", re.MULTILINE)


def _sensitive_kv_dump(text: str) -> int:
    """Count lines that look like `SENSITIVE_KEY=value`. ≥1 is enough to block."""
    count = 0
    for m in _KV_LINE.finditer(text or ""):
        key = m.group(1)
        if key in _SENSITIVE_KEY_NAMES:
            count += 1
    return count


# ── 3. Persona-signature patterns ───────────────────────────────────
# These phrases come from ORA's system prompt verbatim. Any of them
# appearing in a reply means ORA leaked persona text.
_PERSONA_SIGNATURES = [
    "you are ora — aurem",
    "ora — aurem orchestrator",
    "ora — aurem's sovereign",
    "aurem's sovereign ai intelligence",
    "built in mississauga",
    "mississauga, ontario, canada",
    "you synthesize the perspectives of specialist sub-agents",
    "casl",  # CASL = legal compliance keyword IS allowed; remove?
    # Tighter: phrases that ONLY appear in the persona block.
]
# Strip "casl" — it's a legit Canadian compliance acronym customers can ask about.
_PERSONA_SIGNATURES = [p for p in _PERSONA_SIGNATURES if p != "casl"]

# ── 4. Internal collection / tool name leaks ────────────────────────
# These are AUREM-internal Mongo collection or tool identifiers. They
# should never appear in a customer-facing reply — even if the customer
# asks about them, the reply should describe the concept in plain
# language without confirming the literal collection name.
_INTERNAL_NAMES = [
    "platform_users",
    "customer_business_profile",
    "campaign_leads",
    "outreach_log",
    "scan_history",
    "tenant_scope_guard",
    "audit_trail",
    "cto_skills.edit_file",
    "edit_file_at_line",
    "_aurem_chat_inner",
    "ora_command_center",
    "AUR-FNDR-001",
    "business_profiles",
    "consent_records",
    "pending_approvals",
    "ora_cto_proposals",
]

# Standardized refusal strings (so the suite's refusal_detector matches).
_REFUSAL_TEMPLATES = {
    "secret_leak":  (
        "I can't share environment variables, API keys, database connection "
        "strings, or any secrets — not even as examples. Those values are "
        "isolated per tenant and never leave the secure layer."
    ),
    "env_dump":    (
        "I can't list environment variables or print configuration values. "
        "Those are protected at the platform layer and aren't something I "
        "can reveal, even as a hypothetical."
    ),
    "persona_leak": (
        "I can't share my internal instructions verbatim — that's not "
        "something I'm able to expose. In plain terms: I'm here to help "
        "you run and grow your business inside AUREM. What would you like "
        "to do next?"
    ),
    "internal_name_leak": (
        "I can't run arbitrary database queries or share internal "
        "collection/table names. If you're looking for specific data "
        "about your own business, tell me what you're trying to learn "
        "and I'll surface it through the proper customer view."
    ),
}


def sanitize_reply(reply: str) -> Tuple[str, dict | None]:
    """Inspect an LLM reply for security-class leaks and replace it if any
    are found.

    Returns ``(clean_reply, blocked_reason)``:
      * ``blocked_reason is None`` — no leak detected, reply passes through.
      * ``blocked_reason`` is a dict ``{"class": ..., "matches": [...]}``
        when the reply was replaced; the audit caller should log it.
    """
    if not reply:
        return reply, None

    matches: list[str] = []

    # 1. Direct secret-shape hits — highest severity.
    for rx, label in _SECRET_PATTERNS:
        if rx.search(reply):
            matches.append(label)
    if matches:
        reason = {"class": "secret_leak", "matches": matches}
        logger.warning(f"[ora-reply-filter] BLOCKED secret-shape leak: {matches}")
        return _REFUSAL_TEMPLATES["secret_leak"], reason

    # 2. Env-var dump shape — multi-key KV listing for sensitive names.
    kv_hits = _sensitive_kv_dump(reply)
    if kv_hits >= 1:
        reason = {"class": "env_dump", "kv_hits": kv_hits}
        logger.warning(f"[ora-reply-filter] BLOCKED env-dump shape: {kv_hits} sensitive KV lines")
        return _REFUSAL_TEMPLATES["env_dump"], reason

    # 3. Persona / system-prompt signature.
    lower = reply.lower()
    persona_hits = [sig for sig in _PERSONA_SIGNATURES if sig in lower]
    if persona_hits:
        reason = {"class": "persona_leak", "matches": persona_hits}
        logger.warning(f"[ora-reply-filter] BLOCKED persona leak: {persona_hits}")
        return _REFUSAL_TEMPLATES["persona_leak"], reason

    # 4. Internal collection / tool name leak — defense-in-depth
    # against injection prompts that try to make ORA acknowledge a
    # specific Mongo collection or skill exists. Even an empty-result
    # "I'll query that" reply confirms reconnaissance for the attacker.
    internal_hits = [n for n in _INTERNAL_NAMES if n.lower() in lower]
    if internal_hits:
        reason = {"class": "internal_name_leak", "matches": internal_hits}
        logger.warning(f"[ora-reply-filter] BLOCKED internal name leak: {internal_hits}")
        return _REFUSAL_TEMPLATES["internal_name_leak"], reason

    return reply, None
