"""
Value-First Hooks + Canadian Moat — iter 282al-7.

Provides:
  • VALUE_HOOKS              — per-situation × per-channel value offer table
  • get_value_hook(lead, channel, step) → dict
  • CANADIAN_TRUST_SIGNALS   — frontend trust-bar source of truth
  • EMAIL_FOOTER / SMS_FOOTER — composed reply footers (CASL-defensible)

The value-first principle:
  1. OBSERVE — show you know their situation
  2. OFFER VALUE — give something useful BEFORE asking for anything
  3. SOFT CTA — make it easy to say yes
  4. OPT-OUT — always present, never buried

These hooks are *templates* (placeholders only). The composer LLM rewrites
them naturally with the lead's real data — never copies verbatim.
"""
from __future__ import annotations


VALUE_HOOKS = {
    "no_website": {
        "email": {
            "subject": "Found something about {business_name}",
            "value_offer": (
                "We built a free preview of what your website could look "
                "like — using your actual services and {city} location. "
                "No strings attached."
            ),
            "cta": "Worth a 30-second look?",
        },
        "sms": {
            "value_offer": (
                "Free website preview for {business_name}: {short_url}"
            ),
            "cta": "Built using your real info.",
        },
        "whatsapp": {
            "value_offer": (
                "Hi — we built a free website preview for {business_name} "
                "using your actual services and {city} location."
            ),
            "cta": "Worth a 30-second look? {short_url}",
        },
        "linkedin": {
            "value_offer": (
                "Noticed {business_name} doesn't have a site — "
                "so we built a free preview using your real info."
            ),
            "cta": "Worth a look? {short_url}",
        },
    },
    "bad_website": {
        "email": {
            "subject": "Quick thing we noticed about {business_name}'s site",
            "value_offer": (
                "We ran a free scan on your website and found {issue_count} "
                "things stopping customers from finding you. Putting the "
                "full report in your inbox — no charge."
            ),
            "cta": "Report's attached. Want us to fix it?",
        },
        "sms": {
            "value_offer": (
                "Free site report for {business_name} — {issue_count} "
                "issues found: {short_url}"
            ),
            "cta": "Take a look.",
        },
        "whatsapp": {
            "value_offer": (
                "Free scan on {business_name}'s site found "
                "{issue_count} issues — full report here: {short_url}"
            ),
            "cta": "Worth 30 seconds.",
        },
        "linkedin": {
            "value_offer": (
                "Ran a quick audit on {business_name}'s site — "
                "{issue_count} fixable issues hurting your visibility."
            ),
            "cta": "Happy to share the report.",
        },
    },
    "unlinked_mentions": {
        "email": {
            "subject": (
                "{count} sites mention {business_name} — "
                "but don't link to you"
            ),
            "value_offer": (
                "We found {count} websites that talk about your business "
                "but aren't sending you any traffic. That's free customers "
                "going nowhere. Here's the full list:"
            ),
            "cta": "Want us to reclaim them?",
        },
        "sms": {
            "value_offer": (
                "{count} sites mention {business_name} but don't link "
                "to you. Free list: {short_url}"
            ),
            "cta": "Reclaim them?",
        },
        "whatsapp": {
            "value_offer": (
                "Found {count} websites mentioning {business_name} that "
                "don't link to you — free traffic going nowhere."
            ),
            "cta": "Full list: {short_url}",
        },
        "linkedin": {
            "value_offer": (
                "Quick find — {count} sites mention {business_name} "
                "without linking to you. Free customer traffic, untapped."
            ),
            "cta": "Worth a look?",
        },
    },
    "follow_up_step2": {
        "email": {
            "subject": "Quick follow-up — {business_name}",
            "value_offer": (
                "Sent something last week about {business_name}'s online "
                "presence. Spring is when {city} homeowners start "
                "searching for {category} — wanted to make sure you saw it."
            ),
            "cta": "Still free to look: {short_url}",
        },
        "sms": {
            "value_offer": (
                "Sent you something last week about {business_name}'s "
                "online presence. Spring is when {city} homeowners start "
                "searching for {category} — wanted to make sure you saw it."
            ),
            "cta": "Still free to look: {short_url}",
        },
        "whatsapp": {
            "value_offer": (
                "Following up on {business_name} — preview's still live: "
                "{short_url}"
            ),
            "cta": "Worth a peek?",
        },
        "linkedin": {
            "value_offer": (
                "Circling back on {business_name} — that free audit's "
                "still open."
            ),
            "cta": "Take a look: {short_url}",
        },
    },
    "final_step3": {
        "email": {
            "subject": "Last one from us — {business_name}",
            "value_offer": (
                "This is our last message. The free website preview we "
                "built for {business_name} stays live for 7 more days at "
                "{short_url}."
            ),
            "cta": "After that we'll remove it. No hard feelings either way.",
            "ps": (
                "P.S. If the timing's ever right, we're a Canadian team — "
                "we get how trades work here."
            ),
        },
        "sms": {
            "value_offer": (
                "Last note — preview for {business_name} stays live "
                "7 more days: {short_url}"
            ),
            "cta": "No pressure either way.",
        },
        "whatsapp": {
            "value_offer": (
                "Final note — your free preview stays live 7 more days: "
                "{short_url}"
            ),
            "cta": "No hard feelings if it's not the right time.",
        },
        "linkedin": {
            "value_offer": (
                "Last touch from us — that free audit's open another week."
            ),
            "cta": "No pressure either way.",
        },
    },
}


# ─────────────────────────────────────────────────────────────────────
# Canadian trust signals — frontend trust bar + footer source of truth
# ─────────────────────────────────────────────────────────────────────
CANADIAN_TRUST_SIGNALS = [
    {"icon": "🍁", "label": "Canadian-Owned & Operated"},
    {"icon": "📍", "label": "Built in Mississauga, Ontario"},
    {"icon": "⚖️", "label": "CASL Compliant — Always"},
    {"icon": "🔒", "label": "Your Data Stays in Canada"},
    {"icon": "⭐", "label": "Serving Canadian Trades Since 2024"},
]


# ─────────────────────────────────────────────────────────────────────
# Footers (CASL-defensible)
# ─────────────────────────────────────────────────────────────────────
EMAIL_FOOTER = (
    "AUREM is a Canadian-owned platform based in Mississauga, ON. "
    "We help Canadian trades businesses get found online.\n"
    "Reply STOP to opt out.\n"
    "7221 Sigsbee Dr, Mississauga ON L4T 3L6"
)

SMS_FOOTER = "AUREM.ca — Canadian-built. Reply STOP to opt out."

REPORT_BADGE = (
    "🍁 AUREM — Canadian-Owned | Mississauga, ON | CASL Compliant"
)


# ─────────────────────────────────────────────────────────────────────
# get_value_hook — public API
# ─────────────────────────────────────────────────────────────────────
def get_value_hook(lead: dict, channel: str, step: int) -> dict:
    """Return the appropriate value hook for a lead × channel × step.

    Selection logic:
      step 3 → final close hook (always soft)
      step 2 → seasonal follow-up hook
      step 1 → context-specific:
               unlinked_mentions_count > 0 → unlinked_mentions
               not has_website            → no_website
               default                    → bad_website
    """
    lead = lead or {}
    channel = (channel or "email").lower()

    if step == 3:
        return VALUE_HOOKS["final_step3"].get(channel, {})

    if step == 2:
        return VALUE_HOOKS["follow_up_step2"].get(channel, {})

    unlinked = int(lead.get("unlinked_mentions_count") or 0)
    has_website = bool(lead.get("has_website"))

    if unlinked > 0:
        return VALUE_HOOKS["unlinked_mentions"].get(channel, {})

    if not has_website:
        return VALUE_HOOKS["no_website"].get(channel, {})

    return VALUE_HOOKS["bad_website"].get(channel, {})


__all__ = [
    "VALUE_HOOKS",
    "CANADIAN_TRUST_SIGNALS",
    "EMAIL_FOOTER",
    "SMS_FOOTER",
    "REPORT_BADGE",
    "get_value_hook",
]
